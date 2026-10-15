# Retail Mind Customer Android App

This is the Android application wrapper for the existing Retail Mind customer web application.

## Product surfaces

- Customer website: https://retail-mind-web.onrender.com/
- Customer Android app: this module

The app intentionally uses the same production customer web frontend and backend APIs, so website and app stay functionally aligned without maintaining two separate customer implementations.

## Android

- Package: com.retailmind.customer
- Target SDK: 36
- Portrait-first mobile experience
- JavaScript + DOM storage enabled for the Next.js customer application
- Persistent cookies/local storage for customer sessions
- Android back navigation
- Pull-to-refresh
- Offline/retry screen
- External non-http(s) URI handling

## Release signing

Configure a Play Store signing key in the Gradle signing configuration before generating the release AAB. Do not commit keystores or passwords.
