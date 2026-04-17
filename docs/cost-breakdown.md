# Cost Breakdown

## Monthly Costs — First 12 Months (AWS Free Tier)

| Service | Cost | Notes |
|---------|------|-------|
| EC2 t2.micro | **FREE** | 750 hrs/month free for 12 months |
| RDS db.t3.micro | **FREE** | 750 hrs/month free for 12 months |
| Elastic IP | **FREE** | Free when attached to running instance |
| Cloudflare | **FREE** | Free plan (DNS, CDN, DDoS) |
| Vercel | **FREE** | Hobby plan (frontend hosting) |
| UptimeRobot | **FREE** | 50 monitors, 5-min checks |
| Sentry | **FREE** | 5K errors/month |
| Let's Encrypt SSL | **FREE** | Auto-renewing certificates |
| GitHub | **FREE** | Private repos |
| Domain (tradeforge.in) | **₹50/mo** | ~₹600/year |
| **TOTAL** | **₹50/month** | First 12 months |

## Monthly Costs — After Free Tier

| Service | Cost | Notes |
|---------|------|-------|
| EC2 t3.small | ₹1,500 | 2 vCPU, 2GB RAM |
| RDS db.t3.micro | ₹1,200 | 2 vCPU, 1GB RAM, 20GB |
| Elastic IP | ₹0 | Free when attached |
| Cloudflare | ₹0 | Free plan sufficient |
| Vercel | ₹0 | Hobby plan |
| Domain | ₹50 | Annual renewal |
| **TOTAL** | **₹2,750/month** | |

## Scaling Costs (100+ Users)

| Service | Cost | Notes |
|---------|------|-------|
| EC2 t3.medium | ₹3,000 | 2 vCPU, 4GB RAM |
| RDS db.t3.small | ₹2,500 | 2 vCPU, 2GB RAM |
| ElastiCache | ₹1,500 | Managed Redis |
| CloudWatch | ₹500 | Enhanced monitoring |
| SES Email | ₹200 | ~10K emails/month |
| Bandwidth | ₹500 | ~100GB/month |
| **TOTAL** | **₹8,200/month** | |

## Revenue vs Cost (Break-even Analysis)

| Users | Revenue (₹999 Starter) | Revenue (₹2,499 Pro mix) | Costs | Profit |
|-------|------------------------|--------------------------|-------|--------|
| 3 | ₹3,000 | ₹5,000 | ₹2,750 | ₹2,250 |
| 10 | ₹10,000 | ₹17,000 | ₹2,750 | ₹14,250 |
| 50 | ₹50,000 | ₹85,000 | ₹5,000 | ₹80,000 |
| 100 | ₹100,000 | ₹170,000 | ₹8,200 | ₹161,800 |
| 500 | ₹500,000 | ₹850,000 | ₹20,000 | ₹830,000 |

**Break-even: 3 paying users.**

## One-Time Costs

| Item | Cost | Notes |
|------|------|-------|
| Domain registration | ₹600 | Annual |
| Fyers API registration | ₹0 | Free for developers |
| Dhan API registration | ₹0 | Free for developers |
| AWS account | ₹0 | Free to create |

## Cost Optimization Tips

1. **Start with t2.micro** (free tier) for first 12 months
2. **Use Redis on EC2** instead of ElastiCache initially
3. **Vercel free tier** handles frontend perfectly
4. **Cloudflare free** provides CDN + DDoS protection
5. **Reserve instances** when stable: 30-40% savings
6. **Scale vertically first**, horizontally later
