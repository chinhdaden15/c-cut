-- loại mã: order (mua tự động qua QR) | sale (bán tay, vd fanpage) | gift (tặng)
ALTER TABLE licenses ADD COLUMN kind TEXT NOT NULL DEFAULT 'sale';
UPDATE licenses SET kind = 'order' WHERE order_id IS NOT NULL;
