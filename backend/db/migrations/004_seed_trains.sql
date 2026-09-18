-- 004_seed_trains.sql
-- Seeds 20 real Indian Railway trains + 15 key junction stations.
-- Safe to run multiple times: uses INSERT ... ON CONFLICT DO NOTHING.

-- ── Stations ─────────────────────────────────────────────────────────────────
INSERT INTO stations (code, name, zone, latitude, longitude, updated_at)
VALUES
  ('NDLS',  'New Delhi',         'NR',   28.6431,  77.2197, CURRENT_TIMESTAMP),
  ('HWH',   'Howrah Junction',   'ER',   22.5958,  88.3017, CURRENT_TIMESTAMP),
  ('CSTM',  'Mumbai CSMT',       'CR',   18.9400,  72.8347, CURRENT_TIMESTAMP),
  ('MAS',   'Chennai Central',   'SR',   13.0288,  80.1859, CURRENT_TIMESTAMP),
  ('SC',    'Secunderabad Jn',   'SCR',  17.4337,  78.5016, CURRENT_TIMESTAMP),
  ('SBC',   'Bangalore City',    'SR',   12.9565,  77.5960, CURRENT_TIMESTAMP),
  ('NGP',   'Nagpur Junction',   'CR',   21.1460,  79.0882, CURRENT_TIMESTAMP),
  ('ALD',   'Prayagraj Jn',      'NR',   25.4246,  81.8410, CURRENT_TIMESTAMP),
  ('BPL',   'Bhopal Junction',   'CR',   23.1815,  77.4104, CURRENT_TIMESTAMP),
  ('LKO',   'Lucknow Jn',        'NR',   26.8390,  80.9333, CURRENT_TIMESTAMP),
  ('BZA',   'Vijayawada Jn',     'SCR',  16.5062,  80.6480, CURRENT_TIMESTAMP),
  ('ADI',   'Ahmedabad Jn',      'WR',   23.0225,  72.5714, CURRENT_TIMESTAMP),
  ('PNBE',  'Patna Junction',    'ECR',  25.6022,  85.1376, CURRENT_TIMESTAMP),
  ('GHY',   'Guwahati',          'NFR',  26.1445,  91.7362, CURRENT_TIMESTAMP),
  ('JP',    'Jaipur Junction',   'NWR',  26.9196,  75.7887, CURRENT_TIMESTAMP)
ON CONFLICT (code) DO NOTHING;

-- ── Trains ───────────────────────────────────────────────────────────────────
INSERT INTO trains (train_id, train_name, origin_station_code, destination_station_code, route, is_active, current_station_code, updated_at)
VALUES
  ('12001', 'New Bhopal Shatabdi',      'NDLS', 'BPL',  'NDLS-BPL',   true, 'NDLS', CURRENT_TIMESTAMP),
  ('12002', 'Bhopal Shatabdi',          'BPL',  'NDLS', 'BPL-NDLS',   true, 'BPL', CURRENT_TIMESTAMP),
  ('12301', 'Howrah Rajdhani Express',  'HWH',  'NDLS', 'HWH-NDLS',   true, 'ALD', CURRENT_TIMESTAMP),
  ('12302', 'New Delhi Rajdhani',       'NDLS', 'HWH',  'NDLS-HWH',   true, 'NGP', CURRENT_TIMESTAMP),
  ('12309', 'Rajendra Nagar Rajdhani',  'PNBE', 'NDLS', 'PNBE-NDLS',  true, 'LKO', CURRENT_TIMESTAMP),
  ('12622', 'Tamil Nadu SF Express',    'NDLS', 'MAS',  'NDLS-MAS',   true, 'SC', CURRENT_TIMESTAMP),
  ('12627', 'Karnataka Express',        'NDLS', 'SBC',  'NDLS-SBC',   true, 'NGP', CURRENT_TIMESTAMP),
  ('12723', 'Telangana Express',        'NDLS', 'SC',   'NDLS-SC',    true, 'BPL', CURRENT_TIMESTAMP),
  ('12801', 'Purushottam SF Express',   'CSTM', 'NDLS', 'CSTM-NDLS',  true, 'NGP', CURRENT_TIMESTAMP),
  ('12841', 'Coromandel Express',       'HWH',  'MAS',  'HWH-MAS',    true, 'BZA', CURRENT_TIMESTAMP),
  ('12951', 'Mumbai Rajdhani Express',  'CSTM', 'NDLS', 'CSTM-NDLS',  true, 'ADI', CURRENT_TIMESTAMP),
  ('12952', 'New Delhi Rajdhani',       'NDLS', 'CSTM', 'NDLS-CSTM',  true, 'BPL', CURRENT_TIMESTAMP),
  ('13015', 'Kaviguru Express',         'NDLS', 'GHY',  'NDLS-GHY',   true, 'ALD', CURRENT_TIMESTAMP),
  ('20503', 'Agartala Rajdhani',        'NDLS', 'GHY',  'NDLS-GHY',   true, 'PNBE', CURRENT_TIMESTAMP),
  ('12275', 'Duronto Express',          'HWH',  'NDLS', 'HWH-NDLS',   true, 'HWH', CURRENT_TIMESTAMP),
  ('12559', 'Shiv Ganga Express',       'MAS',  'NDLS', 'MAS-NDLS',   true, 'LKO', CURRENT_TIMESTAMP),
  ('22221', 'CSMT Rajdhani Express',    'CSTM', 'NDLS', 'CSTM-NDLS',  true, 'NGP', CURRENT_TIMESTAMP),
  ('12003', 'Lucknow Shatabdi',         'NDLS', 'LKO',  'NDLS-LKO',   true, 'NDLS', CURRENT_TIMESTAMP),
  ('12004', 'New Delhi Shatabdi',       'LKO',  'NDLS', 'LKO-NDLS',   true, 'LKO', CURRENT_TIMESTAMP),
  ('12423', 'Dibrugarh Rajdhani',       'NDLS', 'GHY',  'NDLS-GHY',   true, 'PNBE', CURRENT_TIMESTAMP)
ON CONFLICT (train_id) DO NOTHING;
