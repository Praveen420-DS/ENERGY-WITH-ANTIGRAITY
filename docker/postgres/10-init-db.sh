#!/bin/sh
set -eu

: "${POSTGRES_USER:?POSTGRES_USER is required}"
: "${POSTGRES_DB:?POSTGRES_DB is required}"
: "${EPS_APP_PASSWORD:?EPS_APP_PASSWORD is required}"
: "${EPS_MIGRATOR_PASSWORD:?EPS_MIGRATOR_PASSWORD is required}"
: "${EPS_TEST_PASSWORD:?EPS_TEST_PASSWORD is required}"

psql \
  --username "$POSTGRES_USER" \
  --dbname "$POSTGRES_DB" \
  --set ON_ERROR_STOP=1 \
  --set db_name="$POSTGRES_DB" \
  --set app_password="$EPS_APP_PASSWORD" \
  --set migrator_password="$EPS_MIGRATOR_PASSWORD" \
  --set test_password="$EPS_TEST_PASSWORD" <<'EOSQL'

SELECT format(
  'CREATE ROLE eps_migrator LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
  :'migrator_password'
)
WHERE NOT EXISTS (
  SELECT 1 FROM pg_roles WHERE rolname = 'eps_migrator'
)
\gexec

SELECT format(
  'CREATE ROLE eps_app LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
  :'app_password'
)
WHERE NOT EXISTS (
  SELECT 1 FROM pg_roles WHERE rolname = 'eps_app'
)
\gexec

SELECT format(
  'CREATE ROLE eps_test LOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS PASSWORD %L',
  :'test_password'
)
WHERE NOT EXISTS (
  SELECT 1 FROM pg_roles WHERE rolname = 'eps_test'
)
\gexec

SELECT format(
  'ALTER DATABASE %I OWNER TO eps_migrator',
  :'db_name'
)
\gexec

ALTER SCHEMA public OWNER TO eps_migrator;

REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO eps_app;

SELECT format(
  'GRANT CONNECT ON DATABASE %I TO eps_migrator, eps_app',
  :'db_name'
)
\gexec

GRANT SELECT, INSERT, UPDATE, DELETE
ON ALL TABLES IN SCHEMA public
TO eps_app;

GRANT USAGE, SELECT
ON ALL SEQUENCES IN SCHEMA public
TO eps_app;

ALTER DEFAULT PRIVILEGES FOR ROLE eps_migrator
IN SCHEMA public
GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO eps_app;

ALTER DEFAULT PRIVILEGES FOR ROLE eps_migrator
IN SCHEMA public
GRANT USAGE, SELECT ON SEQUENCES TO eps_app;

SELECT format(
  'CREATE DATABASE energy_prediction_test OWNER eps_test'
)
WHERE NOT EXISTS (
  SELECT 1
  FROM pg_database
  WHERE datname = 'energy_prediction_test'
)
\gexec

GRANT CONNECT ON DATABASE energy_prediction_test TO eps_test;

\connect energy_prediction_test

ALTER SCHEMA public OWNER TO eps_test;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO eps_test;

EOSQL