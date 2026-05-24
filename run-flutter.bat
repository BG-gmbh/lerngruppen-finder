@echo off
cd /d %~dp0\flutter_app
flutter pub get
if "%~1"=="" (
  flutter run -d chrome --dart-define=API_BASE_URL=http://127.0.0.1:5000
) else (
  flutter run %*
)
