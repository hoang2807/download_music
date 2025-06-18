-- Tạo bảng downloads
CREATE TABLE IF NOT EXISTS downloads (
    download_id VARCHAR(64) PRIMARY KEY,
    url VARCHAR(255) NOT NULL,
    status VARCHAR(32) NOT NULL DEFAULT 'pending',
    file_name VARCHAR(255),
    file_path VARCHAR(255),
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Tạo index cho tối ưu query
CREATE INDEX idx_downloads_status ON downloads(status);
CREATE INDEX idx_downloads_updated_at ON downloads(updated_at);