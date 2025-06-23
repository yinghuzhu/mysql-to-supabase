# 项目需求说明书

## 项目名称

**mysql-to-supabase**  
MySQL → Supabase 数据同步工具（MVP 版）

## 项目背景与目标

许多系统仍然使用 MySQL 作为主数据库，但随着 Supabase（PostgreSQL）等新一代云数据库平台的流行，数据迁移和同步的需求日益增长。本项目旨在开发一个简单、可配置的 Python 工具，实现将 MySQL 中指定表的数据高效同步到 Supabase（PostgreSQL），为数据迁移、备份、异构数据整合等场景提供一站式基础解决方案。

## 主要功能（MVP 阶段）

- **配置驱动**：通过 YAML 配置文件，指定 MySQL 源库、Supabase 目标库、需要同步的表及字段映射关系。
- **全量同步**：支持将 MySQL 指定表的全部数据一次性同步到 Supabase。
- **基础增量同步**：支持基于主键或更新时间戳的增量同步（仅插入新数据，主键冲突时可选择跳过或更新）。
- **字段映射**：支持字段名的直接映射（类型自动转换仅限常见类型，复杂类型暂不支持）。
- **命令行工具**：提供简单 CLI，支持一键全量同步和增量同步。

## 不支持/限制（MVP 阶段）

- 不支持断点续传、失败重试、批量优化。
- 不支持复杂字段类型映射（如 JSON、数组、枚举等）。
- 不支持删除同步（MySQL 删除不会同步到 Supabase）。
- 日志仅支持基础的命令行输出，不做持久化。
- 仅支持单表同步，多表需多次配置/执行。

## 技术选型

- **语言**：Python 3.8+
- **依赖库**：
  - `mysql-connector-python` 或 `PyMySQL`（MySQL 数据源）
  - `requests` 或 `httpx`（Supabase REST API 交互）
  - `PyYAML`（配置文件解析）
  - `click` 或 `argparse`（命令行工具）

## 配置文件示例（MVP）

> ⚠️ 敏感信息（如数据库密码、API Key）必须通过环境变量设置，配置文件中用 `${ENV_NAME}` 占位。

```yaml
mysql:
  host: localhost
  port: 3306
  user: root
  password: ${MYSQL_PASSWORD}
  database: source_db

supabase:
  url: https://your-project.supabase.co
  api_key: ${SUPABASE_API_KEY}
  schema: public

table:
  source: supplier_product
  target: supplier_product
  key: id
  # 可选：增量同步的时间戳字段
  timestamp_field: updated_at
  fields:
    - id
    - supplier_id
    - product_code
    - product_status
    - category_id
    - backup_code
    - created_at
    - updated_at
```

### 环境变量设置示例

```sh
export MYSQL_PASSWORD=yourpassword
export SUPABASE_API_KEY=your_anon_or_service_key
```

## 典型流程（MVP）

1. **读取配置**：加载 YAML 配置文件，获取数据库连接信息和同步规则。
2. **连接数据库**：分别连接 MySQL 和 Supabase（REST API 或 PostgreSQL）。
3. **读取数据**：全量模式下读取全部数据，增量模式下读取主键/时间戳大于上次同步点的数据。
4. **数据转换**：按字段名直接映射，常见类型自动转换。
5. **写入 Supabase**：通过 Supabase API 或直连 PostgreSQL，将数据写入目标表。主键冲突时可选择跳过或更新。
6. **输出结果**：命令行输出同步结果和错误信息。

## 增量同步说明（MVP）

- 增量同步基于主键或指定的时间戳字段（如 updated_at）。
- 每次同步后，记录最后同步的主键/时间戳，下次同步时只拉取更大的数据。
- 主键冲突时，默认跳过（可选支持更新）。

## 约束与注意事项（MVP）

- 仅支持 MySQL 到 Supabase（PostgreSQL）。
- 仅支持单表同步。
- 字段类型需兼容，复杂类型需手动处理。
- 同步进度（主键/时间戳）可通过本地文件简单记录。 