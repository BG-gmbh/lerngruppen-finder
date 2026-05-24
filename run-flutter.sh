#!/usr/bin/env bash
set -e
ROOT="$(cd "$(dirname "$0")" && pwd)"
cd "$ROOT/flutter_app"
flutter pub get
if [ "$#" -eq 0 ]; then
  flutter run -d chrome --dart-define=API_BASE_URL=http://127.0.0.1:5000
else
  flutter run "$@"
fi
