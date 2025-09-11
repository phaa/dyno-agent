CREATE TABLE IF NOT EXISTS vehicles (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    weight INT NOT NULL,
    traction TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dynos (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    max_weight INT NOT NULL,
    type TEXT NOT NULL
);
