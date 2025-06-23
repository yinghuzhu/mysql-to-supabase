import yaml
import mysql.connector
import requests
import click
import os
import re
import datetime

CONFIG_PATH = 'config.yaml'

# 递归解析 ${ENV_NAME} 占位符
def resolve_env(val):
    if isinstance(val, str):
        m = re.match(r"^\$\{([A-Z0-9_]+)\}$", val)
        if m:
            env_key = m.group(1)
            env_val = os.environ.get(env_key)
            if env_val is None:
                raise RuntimeError(f"Environment variable {env_key} is not set!")
            return env_val
    return val

def resolve_dict(d):
    for k, v in d.items():
        if isinstance(v, dict):
            resolve_dict(v)
        elif isinstance(v, list):
            d[k] = [resolve_env(i) for i in v]
        else:
            d[k] = resolve_env(v)

# 新增：序列化行，处理datetime/date类型
def serialize_row(row):
    def convert(v):
        if isinstance(v, (datetime.datetime, datetime.date)):
            return v.isoformat()
        return v
    return {k: convert(v) for k, v in row.items()}

# 读取配置
def load_config(path=CONFIG_PATH):
    with open(path, 'r') as f:
        cfg = yaml.safe_load(f)
    resolve_dict(cfg)
    return cfg

# MySQL连接
def get_mysql_conn(cfg):
    return mysql.connector.connect(
        host=cfg['host'],
        port=cfg['port'],
        user=cfg['user'],
        password=cfg['password'],
        database=cfg['database']
    )

# Supabase API写入
def upsert_supabase_row(supa_cfg, table, row, pk):
    url = f"{supa_cfg['url']}/rest/v1/{table}"
    headers = {
        'apikey': supa_cfg['api_key'],
        'Authorization': f"Bearer {supa_cfg['api_key']}",
        'Content-Type': 'application/json',
        'Prefer': f"resolution=merge-duplicates"
    }
    row = serialize_row(row)  # 修复datetime序列化
    resp = requests.post(url, json=[row], headers=headers)
    if resp.ok:
        print(f"upsert row: {row['id']}")
    else:
        print(f"[ERROR] Failed to upsert row: {resp.text}")
    
    return resp

# 获取上次同步点（本地文件）
def get_last_sync_point(table, key):
    fname = f".last_sync_{table}_{key}"
    if os.path.exists(fname):
        with open(fname, 'r') as f:
            return f.read().strip()
    return None

def set_last_sync_point(table, key, value):
    fname = f".last_sync_{table}_{key}"
    with open(fname, 'w') as f:
        f.write(str(value))

@click.group()
def cli():
    pass

@cli.command()
def full():
    """全量同步"""
    cfg = load_config()
    mysql_cfg = cfg['mysql']
    supa_cfg = cfg['supabase']
    tbl_cfg = cfg['table']
    conn = get_mysql_conn(mysql_cfg)
    cursor = conn.cursor(dictionary=True)
    fields = ','.join(tbl_cfg['fields'])
    cursor.execute(f"SELECT {fields} FROM {tbl_cfg['source']}")
    rows = cursor.fetchall()
    print(f"[INFO] Fetched {len(rows)} rows from MySQL.")
    for row in rows:
        upsert_supabase_row(supa_cfg, tbl_cfg['target'], row, tbl_cfg['key'])
    print("[INFO] Full sync done.")
    if 'timestamp_field' in tbl_cfg:
        if rows:
            set_last_sync_point(tbl_cfg['target'], tbl_cfg['timestamp_field'], rows[-1][tbl_cfg['timestamp_field']])
        else:
            set_last_sync_point(tbl_cfg['target'], tbl_cfg['timestamp_field'], '')
    else:
        if rows:
            set_last_sync_point(tbl_cfg['target'], tbl_cfg['key'], rows[-1][tbl_cfg['key']])
        else:
            set_last_sync_point(tbl_cfg['target'], tbl_cfg['key'], '')

@cli.command()
def incr():
    """增量同步"""
    cfg = load_config()
    mysql_cfg = cfg['mysql']
    supa_cfg = cfg['supabase']
    tbl_cfg = cfg['table']
    conn = get_mysql_conn(mysql_cfg)
    cursor = conn.cursor(dictionary=True)
    fields = ','.join(tbl_cfg['fields'])
    # 增量同步点
    if 'timestamp_field' in tbl_cfg:
        last = get_last_sync_point(tbl_cfg['target'], tbl_cfg['timestamp_field'])
        cond = f"WHERE {tbl_cfg['timestamp_field']} > '{last}'" if last else ''
        sql = f"SELECT {fields} FROM {tbl_cfg['source']} {cond} ORDER BY {tbl_cfg['timestamp_field']} ASC"
    else:
        last = get_last_sync_point(tbl_cfg['target'], tbl_cfg['key'])
        cond = f"WHERE {tbl_cfg['key']} > {last}" if last else ''
        sql = f"SELECT {fields} FROM {tbl_cfg['source']} {cond} ORDER BY {tbl_cfg['key']} ASC"
    cursor.execute(sql)
    rows = cursor.fetchall()
    print(f"[INFO] Fetched {len(rows)} rows for incremental sync.")
    for row in rows:
        upsert_supabase_row(supa_cfg, tbl_cfg['target'], row, tbl_cfg['key'])
    print("[INFO] Incremental sync done.")
    if rows:
        if 'timestamp_field' in tbl_cfg:
            set_last_sync_point(tbl_cfg['target'], tbl_cfg['timestamp_field'], rows[-1][tbl_cfg['timestamp_field']])
        else:
            set_last_sync_point(tbl_cfg['target'], tbl_cfg['key'], rows[-1][tbl_cfg['key']])

if __name__ == '__main__':
    cli() 