// ================================================
// MongoDB — Initialization Script
// ================================================
// Runs on first container start to set up the database,
// create collections, and apply indexes.

db = db.getSiblingDB("energy_prediction");

// --- Create Collections ---
db.createCollection("users");
db.createCollection("meters");
db.createCollection("energy_readings", {
    timeseries: {
        timeField: "timestamp",
        metaField: "meter_id",
        granularity: "minutes"
    }
});
db.createCollection("weather_data");
db.createCollection("predictions");
db.createCollection("anomalies");
db.createCollection("models");
db.createCollection("alert_configs");
db.createCollection("audit_logs");

// --- Indexes: users ---
db.users.createIndex({ email: 1 }, { unique: true });
db.users.createIndex({ role: 1 });

// --- Indexes: meters ---
db.meters.createIndex({ meter_id: 1 }, { unique: true });
db.meters.createIndex({ owner_id: 1 });
db.meters.createIndex({ "location.building": 1, "location.zone": 1 });

// --- Indexes: energy_readings ---
db.energy_readings.createIndex({ meter_id: 1, timestamp: -1 });

// --- Indexes: weather_data ---
db.weather_data.createIndex({ location_key: 1, timestamp: -1 });

// --- Indexes: predictions ---
db.predictions.createIndex({ meter_id: 1, target_start: -1 });
db.predictions.createIndex({ model_id: 1 });

// --- Indexes: anomalies ---
db.anomalies.createIndex({ meter_id: 1, timestamp: -1 });
db.anomalies.createIndex({ severity: 1, is_resolved: 1 });

// --- Indexes: models ---
db.models.createIndex({ status: 1, horizon: 1 });
db.models.createIndex({ algorithm: 1 });

// --- Indexes: alert_configs ---
db.alert_configs.createIndex({ user_id: 1, is_enabled: 1 });

// --- Indexes: audit_logs ---
db.audit_logs.createIndex({ timestamp: -1 }, { expireAfterSeconds: 7776000 }); // 90-day TTL
db.audit_logs.createIndex({ user_id: 1, action: 1 });

print("✅ Database initialized with collections and indexes.");
