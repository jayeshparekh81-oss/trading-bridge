# Launch Checklist

## Infrastructure

- [ ] AWS account created and billing alarm set (₹5,000 threshold)
- [ ] Domain purchased (tradeforge.in)
- [ ] EC2 instance running (Ubuntu 22.04)
- [ ] Elastic IP attached
- [ ] RDS PostgreSQL configured
- [ ] Security groups restricted (DB only from EC2)
- [ ] SSH key-only access (password auth disabled)
- [ ] UFW firewall enabled (22, 80, 443 only)
- [ ] Cloudflare DNS configured
- [ ] SSL certificate installed (Let's Encrypt)
- [ ] DNS propagated (check with `dig tradeforge.in`)

## Backend

- [ ] `.env.production` configured with real values
- [ ] **NEW Fernet key generated** (not dev key!)
- [ ] **NEW JWT secret generated** (not dev secret!)
- [ ] Database migrated (`alembic upgrade head`)
- [ ] Admin user seeded
- [ ] All Docker services running (`docker compose ps`)
- [ ] Health endpoint responding: `https://api.tradeforge.in/health`
- [ ] API docs accessible: `https://api.tradeforge.in/docs`
- [ ] Celery worker processing tasks
- [ ] Celery beat scheduling running

## Frontend

- [ ] Vercel deployed
- [ ] `NEXT_PUBLIC_API_URL` set to `https://api.tradeforge.in`
- [ ] Custom domain working: `https://tradeforge.in`
- [ ] All 21 pages loading
- [ ] Dark mode renders correctly
- [ ] Mobile responsive verified

## End-to-End Testing

- [ ] Register a new user → success
- [ ] Login → dashboard loads
- [ ] Add broker credentials → encrypted and saved
- [ ] Create webhook token → URL generated
- [ ] View kill switch status → shows ACTIVE
- [ ] Update kill switch config → saves correctly
- [ ] View trade history → loads (empty is OK for new user)
- [ ] Update profile → saves
- [ ] Change password → works
- [ ] Logout → redirects to login
- [ ] Login again with new password → works
- [ ] Admin panel accessible (admin user) → system health shows

## Notifications

- [ ] AWS SES configured and verified sender email
- [ ] Welcome email sent on registration
- [ ] Telegram bot token configured
- [ ] Test notification sent successfully

## Monitoring

- [ ] UptimeRobot: frontend monitor active
- [ ] UptimeRobot: backend health monitor active
- [ ] Email alerts configured for downtime
- [ ] Log access verified (`docker compose logs`)
- [ ] Database backups verified (RDS automated)

## Security

- [ ] Production encryption keys are NEW (not dev keys)
- [ ] SSH root login disabled
- [ ] UFW firewall active
- [ ] RDS not publicly accessible
- [ ] CORS restricted to production domains
- [ ] Rate limiting active (Nginx + application)
- [ ] HTTPS enforced (HTTP redirects to HTTPS)
- [ ] Security headers present (check headers at securityheaders.com)

## Legal & Compliance

- [ ] Terms & Conditions page ready
- [ ] Privacy Policy page ready
- [ ] Trading Risk Disclaimer page ready
- [ ] Refund Policy documented
- [ ] Contact information visible
- [ ] SEBI compliance notes reviewed

## Marketing (Pre-Launch)

- [ ] Twitter/X account created
- [ ] LinkedIn page created
- [ ] YouTube channel created
- [ ] Telegram group created
- [ ] Launch announcement drafted
- [ ] First 10 beta testers identified
- [ ] Feedback form ready

## Post-Launch (First Week)

- [ ] Monitor error rates daily
- [ ] Check uptime reports
- [ ] Respond to user feedback within 24 hours
- [ ] Fix any reported bugs immediately
- [ ] Send daily summary of platform health
- [ ] Backup database manually (verify RDS snapshots)
- [ ] Review audit logs for suspicious activity
