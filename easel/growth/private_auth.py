"""Opt-in production authentication. Never initializes the local/default database."""
import argparse
from contextlib import closing
from getpass import getpass
import hashlib
import hmac
from pathlib import Path
import re
import secrets
import sqlite3
import time
from uuid import uuid4

from .accounts import AccountRepository
from .database import Database
from .repository import NotFound


def digest(value):
    return hashlib.sha256(value.encode()).hexdigest()


def password_hash(password, salt):
    return hashlib.scrypt(password.encode(), salt=bytes.fromhex(salt), n=16384, r=8, p=1).hex()


class AuthStore:
    def __init__(self, root):
        self.root = Path(root).resolve()
        self.database = Database(self.root / 'growth.sqlite3')

    def initialize(self):
        # A populated legacy database requires a separately authorized migration.
        if self.database.path.exists():
            with closing(self.database.connect()) as conn:
                tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
                if 'private_auth_version' not in tables and 'accounts' in tables and conn.execute('SELECT 1 FROM accounts LIMIT 1').fetchone():
                    raise RuntimeError('Refusing historical database; use a new empty data directory')
        self.database.initialize()
        with self.database.transaction() as conn:
            for sql in (
                'CREATE TABLE IF NOT EXISTS private_auth_version(version INTEGER PRIMARY KEY CHECK(version=1))',
                'INSERT OR IGNORE INTO private_auth_version VALUES(1)',
                'CREATE TABLE IF NOT EXISTS private_users(id TEXT PRIMARY KEY, username TEXT UNIQUE NOT NULL, salt TEXT NOT NULL, password_hash TEXT NOT NULL, enabled INTEGER NOT NULL DEFAULT 1)',
                'CREATE TABLE IF NOT EXISTS private_sessions(token_hash TEXT PRIMARY KEY, user_id TEXT NOT NULL REFERENCES private_users(id) ON DELETE CASCADE, expires_at REAL NOT NULL)',
                'CREATE TABLE IF NOT EXISTS account_owners(account_id TEXT PRIMARY KEY REFERENCES accounts(id) ON DELETE CASCADE, user_id TEXT NOT NULL REFERENCES private_users(id))',
                'CREATE INDEX IF NOT EXISTS account_owner_user ON account_owners(user_id)',
                'CREATE TABLE IF NOT EXISTS private_limits(bucket TEXT NOT NULL, at REAL NOT NULL)',
                'CREATE INDEX IF NOT EXISTS private_limits_bucket ON private_limits(bucket,at)',
            ):
                conn.execute(sql)

    def ready(self):
        if not self.database.path.is_file():
            raise RuntimeError('Initialize a fresh production directory and provision a user first')
        with closing(self.database.connect()) as conn:
            if not conn.execute('SELECT 1 FROM private_auth_version WHERE version=1').fetchone():
                raise RuntimeError('Production authentication is not initialized')
            if not conn.execute('SELECT 1 FROM private_users WHERE enabled=1 LIMIT 1').fetchone():
                raise RuntimeError('Provision at least one enabled user')

    def create_user(self, username, password):
        if not re.fullmatch(r'[A-Za-z0-9_.-]{3,40}', username) or not 12 <= len(password) <= 200:
            raise ValueError('Username: 3–40 ASCII letters/digits/_.-; password: 12–200 characters')
        uid, salt = str(uuid4()), secrets.token_hex(16)
        hashed = password_hash(password, salt)
        with self.database.transaction() as conn:
            conn.execute('INSERT INTO private_users VALUES(?,?,?,?,1)', (uid, username, salt, hashed))
        return uid

    def login(self, username, password):
        with closing(self.database.connect()) as conn:
            row = conn.execute('SELECT * FROM private_users WHERE username=?', (username,)).fetchone()
        computed = password_hash(password[:201], row['salt'] if row else '00' * 16)
        if not row or not row['enabled'] or len(password) > 200 or not hmac.compare_digest(computed, row['password_hash']):
            return None
        token = secrets.token_urlsafe(32)
        with self.database.transaction() as conn:
            conn.execute('DELETE FROM private_sessions WHERE expires_at<=?', (time.time(),))
            conn.execute('INSERT INTO private_sessions VALUES(?,?,?)', (digest(token), row['id'], time.time() + 8*3600))
        return token

    def user(self, token):
        with closing(self.database.connect()) as conn:
            row = conn.execute('SELECT u.id FROM private_sessions s JOIN private_users u ON u.id=s.user_id WHERE s.token_hash=? AND s.expires_at>? AND u.enabled=1', (digest(token), time.time())).fetchone()
            return row[0] if row else None

    def logout(self, token):
        with self.database.transaction() as conn:
            conn.execute('DELETE FROM private_sessions WHERE token_hash=?', (digest(token),))

    def disable(self, username):
        with self.database.transaction() as conn:
            conn.execute('UPDATE private_users SET enabled=0 WHERE username=?', (username,))
            conn.execute('DELETE FROM private_sessions WHERE user_id IN (SELECT id FROM private_users WHERE username=?)', (username,))

    def owns(self, uid, aid):
        with closing(self.database.connect()) as conn:
            return conn.execute('SELECT 1 FROM account_owners WHERE user_id=? AND account_id=?', (uid, aid)).fetchone() is not None

    def take(self, bucket, limit, seconds):
        now = time.time()
        with self.database.transaction() as conn:
            conn.execute('DELETE FROM private_limits WHERE at<?', (now - 86400,))
            if conn.execute('SELECT COUNT(*) FROM private_limits WHERE bucket=? AND at>?', (bucket, now-seconds)).fetchone()[0] >= limit:
                return False
            conn.execute('INSERT INTO private_limits VALUES(?,?)', (bucket, now))
            return True


class OwnedAccounts(AccountRepository):
    def __init__(self, store, uid):
        super().__init__(store.database)
        self.uid = uid

    def _get(self, conn, table, entity_id, account_id):
        if not conn.execute('SELECT 1 FROM account_owners WHERE user_id=? AND account_id=?', (self.uid, account_id)).fetchone():
            raise NotFound('Account not found')
        return super()._get(conn, table, entity_id, account_id)

    def _insert(self, conn, table, **data):
        record = super()._insert(conn, table, **data)
        if table == 'accounts':
            conn.execute('INSERT INTO account_owners VALUES(?,?)', (record.id, self.uid))
        return record

    def state(self, account_id):
        with closing(self.database.connect()) as conn:
            accounts = [self._record('accounts', r) for r in conn.execute('SELECT a.* FROM accounts a JOIN account_owners o ON o.account_id=a.id WHERE o.user_id=? ORDER BY a.created_at,a.id', (self.uid,))]
        if account_id is None and not accounts:
            return dict(accounts=[], account=None, profiles=[], diagnoses=[], runs=[], projections=[], current_profile=None, current_diagnosis=None, counts=dict(research=0, topics=0, drafts=0), next_step='完成账号建档')
        result = super().state(account_id or accounts[0].id)
        result['accounts'] = accounts
        return result


def backup(source, destination):
    destination = Path(destination)
    # Exclusive reservation: never replace a previous backup or live database.
    with destination.open('xb'):
        pass
    with closing(sqlite3.connect(f'{Path(source).resolve().as_uri()}?mode=ro', uri=True)) as src, closing(sqlite3.connect(destination)) as dst:
        src.backup(dst)
        if dst.execute('PRAGMA integrity_check').fetchone()[0] != 'ok':
            raise RuntimeError('Backup integrity check failed')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--data-dir', required=True, type=Path)
    sub = parser.add_subparsers(dest='action', required=True)
    sub.add_parser('init')
    sub.add_parser('create-user').add_argument('username')
    sub.add_parser('disable-user').add_argument('username')
    sub.add_parser('backup').add_argument('destination', type=Path)
    args = parser.parse_args()
    store = AuthStore(args.data_dir)
    if args.action == 'init':
        store.initialize()
    elif args.action == 'create-user':
        password = getpass('Password (hidden): ')
        if password != getpass('Repeat password (hidden): '):
            raise SystemExit('Passwords differ; nothing changed')
        store.create_user(args.username, password)
    elif args.action == 'disable-user':
        store.disable(args.username)
    else:
        backup(store.database.path, args.destination)
    print('Completed; no credentials printed.')


if __name__ == '__main__':
    main()
