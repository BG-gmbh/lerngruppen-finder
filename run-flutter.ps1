param(
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$Args
)
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location "$Root/flutter_app"
flutter pub get
if ($Args.Count -eq 0) {
    flutter run -d chrome --dart-define=API_BASE_URL=http://127.0.0.1:5000
} else {
    flutter run @Args
}
