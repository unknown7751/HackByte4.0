-- scripts/init-postgis.sql
-- Runs once on first container start to enable PostGIS extensions.

CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_topology;
CREATE EXTENSION IF NOT EXISTS fuzzystrmatch;         -- useful for geocoding helpers
CREATE EXTENSION IF NOT EXISTS postgis_tiger_geocoder; -- optional, remove if not needed

