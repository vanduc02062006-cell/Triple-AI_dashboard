# Dashboard Report Notes & Methodology
- NPU = user có first successful payment transaction gắn với promotion/campaign.
- Chỉ dùng transStatus = 1 để xác định NPU.
- campaignID = 0 không được xem là acquisition campaign.
- campaignID = 0 vẫn quan trọng để đo post-first non-promo behavior.
- Promotion anomaly được gắn nhãn unknown_promotion, không xóa.
- userChargeAmount không được dùng làm metric value chính vì có anomaly userChargeAmount > amount.
- Dashboard dùng cho monitor và compare, không dùng để kết luận nhân quả.
- Final campaign quality score sẽ được xây ở notebook sau.
