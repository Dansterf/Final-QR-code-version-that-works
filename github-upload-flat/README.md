# QR Check-In System for Doulos Education

A complete QR code-based check-in system with QuickBooks integration for tutoring programs.

## ✨ Features

- ✅ Customer registration with automatic QR code generation
- ✅ Email delivery of QR codes (as downloadable attachments)
- ✅ QR code scanning for check-ins (camera + manual entry)
- ✅ Check-in history tracking
- ✅ QuickBooks Online integration for billing
- ✅ Support for multiple session types (French Tutoring, Math Tutoring, Music Sessions)
- ✅ Mobile-responsive design

## 🚀 Quick Deploy to Railway

1. **Fork/Clone this repository**

2. **Push to GitHub**
   ```bash
   git init
   git add .
   git commit -m "Initial commit"
   git remote add origin YOUR_REPO_URL
   git push -u origin main
   ```

3. **Deploy on Railway**
   - Go to https://railway.app/
   - Click "New Project" → "Deploy from GitHub repo"
   - Select this repository
   - Add environment variables (see below)

4. **Set Environment Variables in Railway**
   ```
   SENDGRID_API_KEY=your_sendgrid_api_key
   SENDGRID_FROM_EMAIL=info@doulos.education
   QB_CLIENT_ID=your_quickbooks_client_id
   QB_CLIENT_SECRET=your_quickbooks_client_secret
   QB_ENVIRONMENT=production
   QB_REDIRECT_URI=https://your-app.up.railway.app/api/quickbooks/callback
   QR_CHECKIN_DB_PATH=./data
   ```

5. **Update QuickBooks Developer Portal**
   - Add your Railway URL as redirect URI
   - Format: `https://your-app.up.railway.app/api/quickbooks/callback`

6. **Done!** Visit your Railway URL to use the app.

## 📚 Full Documentation

See `RAILWAY_DEPLOYMENT_GUIDE.md` for detailed step-by-step instructions.

## 🔧 Tech Stack

- **Backend:** Flask (Python)
- **Frontend:** React + Vite
- **Database:** SQLite (with persistent storage)
- **Email:** SendGrid
- **Payments:** QuickBooks Online
- **Deployment:** Railway (recommended)

## 📝 API Endpoints

- `POST /api/customers` - Register new customer
- `GET /api/customers` - List all customers
- `POST /api/checkins` - Record check-in
- `GET /api/checkins` - Get check-in history
- `GET /api/quickbooks/status` - QuickBooks connection status
- `POST /api/email/send-qr-email` - Send QR code via email

## 🎯 What's Fixed in This Version

✅ **Email Delivery** - QR codes now sent reliably as attachments  
✅ **QuickBooks Persistence** - Connection stays active across refreshes  
✅ **Backend QR Generation** - Faster and more reliable  
✅ **Railway Ready** - Optimized for Railway deployment  

## 🆘 Support

For issues or questions:
1. Check the deployment guide
2. Review Railway logs
3. Verify environment variables are set correctly

## 📄 License

Proprietary - Doulos Education Tutoring Program

---

**Ready to deploy? Follow the Quick Deploy steps above!** 🚀

