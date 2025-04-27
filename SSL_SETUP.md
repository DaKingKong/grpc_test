# Setting up SSL for the gRPC Server

This guide explains how to set up SSL certificates for securing the gRPC connection between your client and EC2 server.

## Option 1: Using Let's Encrypt (Recommended for Production)

If you have a domain name pointing to your EC2 instance, you can use Let's Encrypt to get free SSL certificates:

1. SSH into your EC2 instance
2. Install certbot:
   ```bash
   sudo apt-get update
   sudo apt-get install certbot
   ```
3. Obtain SSL certificates (replace `yourdomain.com` with your actual domain):
   ```bash
   sudo certbot certonly --standalone -d yourdomain.com
   ```
4. Once successful, your certificates will be located at:
   - Certificate: `/etc/letsencrypt/live/yourdomain.com/fullchain.pem`
   - Private key: `/etc/letsencrypt/live/yourdomain.com/privkey.pem`

5. Set environment variables for your server:
   ```bash
   export SSL_CERT_FILE=/etc/letsencrypt/live/yourdomain.com/fullchain.pem
   export SSL_KEY_FILE=/etc/letsencrypt/live/yourdomain.com/privkey.pem
   ```

## Option 2: Self-Signed Certificates (For Testing)

For testing purposes, you can generate self-signed certificates:

1. Install OpenSSL:
   ```bash
   sudo apt-get install openssl
   ```

2. Generate a private key:
   ```bash
   openssl genrsa -out server.key 2048
   ```

3. Create a self-signed certificate:
   ```bash
   openssl req -new -x509 -key server.key -out server.crt -days 365
   ```

4. Set environment variables:
   ```bash
   export SSL_CERT_FILE=/path/to/server.crt
   export SSL_KEY_FILE=/path/to/server.key
   ```

## Updating Your Client

When using SSL certificates, your client needs to use a secure channel:

```python
# For production with valid certificates:
channel = grpc.secure_channel('your-server-address:443', grpc.ssl_channel_credentials())

# For testing with self-signed certificates (INSECURE - only for development):
channel = grpc.secure_channel('your-server-address:443', 
                              grpc.ssl_channel_credentials(root_certificates=None),
                              options=(('grpc.ssl_target_name_override', 'your-server-address'),))
```

## Troubleshooting

### Common SSL/TLS issues:

1. **Wrong version number**: This usually happens when you try to use SSL on a connection that doesn't support it, or vice versa. Make sure both client and server are configured correctly.

2. **Certificate verification failed**: If using self-signed certificates, you may need to disable verification on the client (not recommended for production).

3. **Certificate name mismatch**: The domain name in the certificate must match the server address being used. 