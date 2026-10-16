#!/bin/sh
# DBA bootstrap (12 §0): roles with passwords + database owned by erp_migrator.
# Runs once from /docker-entrypoint-initdb.d as the postgres superuser.
set -eu
psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname postgres \
  -v db="${ERP_DB_NAME:-erp}" \
  -v migrator_pw="${ERP_MIGRATOR_PASSWORD:?}" \
  -v app_pw="${ERP_APP_PASSWORD:?}" <<'SQL'
CREATE ROLE erp_migrator LOGIN NOSUPERUSER CREATEDB NOCREATEROLE PASSWORD :'migrator_pw';
CREATE ROLE erp_app LOGIN NOSUPERUSER NOBYPASSRLS PASSWORD :'app_pw';
CREATE ROLE erp_system NOLOGIN BYPASSRLS;
-- the migrator owns every object and hands SECURITY DEFINER functions to erp_system
GRANT erp_system TO erp_migrator;
ALTER ROLE erp_app SET search_path = app, platform, public;
ALTER ROLE erp_system SET search_path = app, auth, platform, public;
CREATE DATABASE :"db" OWNER erp_migrator;
SQL
