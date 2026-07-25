SELECT 'CREATE DATABASE energy_prediction_test'
WHERE NOT EXISTS (
    SELECT FROM pg_database WHERE datname = 'energy_prediction_test'
)\gexec
