import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter/services.dart';
import 'package:http/http.dart' as http;
import 'package:shared_preferences/shared_preferences.dart';

const apiBaseUrl = String.fromEnvironment(
  'API_BASE_URL',
  defaultValue: 'http://127.0.0.1:5000',
);

void main() {
  runApp(const LernApp());
}

class LernApp extends StatelessWidget {
  const LernApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'lerngruppen finder',
      debugShowCheckedModeBanner: false,
      theme: ThemeData(
        colorScheme: ColorScheme.fromSeed(
          seedColor: const Color(0xff3d9cf5),
          brightness: Brightness.dark,
          surface: const Color(0xff1a222d),
        ),
        scaffoldBackgroundColor: const Color(0xff0f1419),
        inputDecorationTheme: const InputDecorationTheme(
          border: OutlineInputBorder(),
        ),
        useMaterial3: true,
      ),
      home: const AppShell(),
    );
  }
}

class ApiClient {
  ApiClient({required this.baseUrl, this.token});

  final String baseUrl;
  String? token;

  Uri uri(String path, [Map<String, String>? query]) {
    return Uri.parse('$baseUrl$path').replace(queryParameters: query);
  }

  Map<String, String> get headers {
    return {
      'Accept': 'application/json',
      if (token != null) 'Authorization': 'Bearer $token',
    };
  }

  Future<Map<String, dynamic>> getJson(
    String path, [
    Map<String, String>? query,
  ]) async {
    final response = await http.get(uri(path, query), headers: headers);
    return _decode(response);
  }

  Future<Map<String, dynamic>> postJson(
    String path,
    Map<String, dynamic> body,
  ) async {
    final response = await http.post(
      uri(path),
      headers: {...headers, 'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> putJson(
    String path,
    Map<String, dynamic> body,
  ) async {
    final response = await http.put(
      uri(path),
      headers: {...headers, 'Content-Type': 'application/json'},
      body: jsonEncode(body),
    );
    return _decode(response);
  }

  Future<Map<String, dynamic>> deleteJson(String path) async {
    final response = await http.delete(uri(path), headers: headers);
    return _decode(response);
  }

  Future<Map<String, dynamic>> _decode(http.Response response) async {
    Map<String, dynamic> decoded;
    try {
      decoded = response.body.isEmpty
          ? <String, dynamic>{}
          : jsonDecode(response.body) as Map<String, dynamic>;
    } on FormatException {
      final preview = response.body
          .replaceAll(RegExp(r'\s+'), ' ')
          .trim();
      final shortPreview = preview.length > 80
          ? '${preview.substring(0, 80)}...'
          : preview;
      throw ApiException(
        'invalid_json',
        'Der Server hat kein JSON geliefert. Backend neu starten und '
            'API_BASE_URL pruefen. Status ${response.statusCode}: $shortPreview',
      );
    }
    if (response.statusCode < 200 || response.statusCode >= 300) {
      throw ApiException(
        decoded['error']?.toString() ?? 'request_failed',
        decoded['message']?.toString(),
      );
    }
    return decoded;
  }
}

class ApiException implements Exception {
  const ApiException(this.code, [this.message]);

  final String code;
  final String? message;

  @override
  String toString() => message ?? code;
}

class UserProfile {
  const UserProfile({
    required this.userId,
    required this.username,
    required this.role,
    required this.school,
    required this.levelGerman,
    required this.levelMath,
    required this.levelEnglish,
    required this.contactEmail,
    required this.notifyLadenEmail,
    required this.schoolLogoUrl,
  });

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      userId: json['user_id'] as int,
      username: json['username']?.toString() ?? '',
      role: json['role']?.toString() ?? 'user',
      school: json['school']?.toString() ?? '',
      levelGerman: json['level_german']?.toString() ?? 'noob',
      levelMath: json['level_math']?.toString() ?? 'noob',
      levelEnglish: json['level_english']?.toString() ?? 'noob',
      contactEmail: json['contact_email']?.toString() ?? '',
      notifyLadenEmail: json['notify_laden_email'] == true,
      schoolLogoUrl: json['school_logo_url']?.toString() ?? '',
    );
  }

  final int userId;
  final String username;
  final String role;
  final String school;
  final String levelGerman;
  final String levelMath;
  final String levelEnglish;
  final String contactEmail;
  final bool notifyLadenEmail;
  final String schoolLogoUrl;

  String levelFor(String subject) {
    return switch (subject) {
      'german' => levelGerman,
      'math' => levelMath,
      'english' => levelEnglish,
      _ => 'noob',
    };
  }
}

class AppShell extends StatefulWidget {
  const AppShell({super.key});

  @override
  State<AppShell> createState() => _AppShellState();
}

class _AppShellState extends State<AppShell> {
  final api = ApiClient(baseUrl: apiBaseUrl);
  UserProfile? user;
  int tab = 0;
  bool loading = true;
  String? error;

  @override
  void initState() {
    super.initState();
    _restoreSession();
  }

  Future<void> _restoreSession() async {
    final prefs = await SharedPreferences.getInstance();
    final token = prefs.getString('api_token');
    if (token == null) {
      setState(() => loading = false);
      return;
    }
    api.token = token;
    try {
      final me = await api.getJson('/api/me');
      setState(() {
        user = UserProfile.fromJson(me);
        loading = false;
      });
    } catch (_) {
      await prefs.remove('api_token');
      setState(() {
        api.token = null;
        loading = false;
      });
    }
  }

  Future<void> _login(String username, String password) async {
    final data = await api.postJson('/api/login', {
      'username': username,
      'password': password,
    });
    await _storeAuth(data);
  }

  Future<void> _redeemInvite(
    String code,
    String username,
    String password,
    String passwordConfirm,
  ) async {
    final data = await api.postJson('/api/invite', {
      'code': code,
      'username': username,
      'password': password,
      'password_confirm': passwordConfirm,
    });
    await _storeAuth(data);
  }

  Future<void> _setupAdmin(
    String username,
    String password,
    String passwordConfirm,
  ) async {
    final data = await api.postJson('/api/setup', {
      'username': username,
      'password': password,
      'password_confirm': passwordConfirm,
    });
    await _storeAuth(data);
  }

  Future<void> _storeAuth(Map<String, dynamic> data) async {
    api.token = data['token']?.toString();
    final prefs = await SharedPreferences.getInstance();
    await prefs.setString('api_token', api.token!);
    setState(() {
      user = UserProfile.fromJson(data['user'] as Map<String, dynamic>);
      error = null;
    });
  }

  Future<void> _logout() async {
    try {
      await api.postJson('/api/logout', {});
    } catch (_) {
      // Local logout still matters if the server is unreachable.
    }
    final prefs = await SharedPreferences.getInstance();
    await prefs.remove('api_token');
    setState(() {
      api.token = null;
      user = null;
      tab = 0;
    });
  }

  Future<void> _refreshMe() async {
    final me = await api.getJson('/api/me');
    setState(() => user = UserProfile.fromJson(me));
  }

  @override
  Widget build(BuildContext context) {
    if (loading) {
      return const Scaffold(body: Center(child: CircularProgressIndicator()));
    }
    if (user == null) {
      return LoginScreen(
        onLogin: _login,
        onInvite: _redeemInvite,
        onSetupAdmin: _setupAdmin,
        error: error,
      );
    }

    final isAdmin = user!.role == 'admin' || user!.role == 'dev';
    final pages = [
      DashboardScreen(
        user: user!,
        onOpenChat: () => setState(() => tab = 1),
        onOpenShop: () => setState(() => tab = 2),
        onOpenAdmin: isAdmin ? () => setState(() => tab = 4) : null,
      ),
      ChatScreen(api: api, user: user!),
      ShopScreen(api: api),
      SettingsScreen(api: api, user: user!, onSaved: _refreshMe),
      if (isAdmin)
        AdminScreen(
          api: api,
          isDev: user!.role == 'dev',
          onAppSettingsSaved: _refreshMe,
        ),
    ];
    final selectedTab = tab < pages.length ? tab : 0;

    return Scaffold(
      appBar: AppBar(
        title: const Text('lerngruppen finder'),
        actions: [
          if (user!.schoolLogoUrl.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 8, horizontal: 6),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(4),
                child: Image.network(
                  user!.schoolLogoUrl,
                  width: 40,
                  height: 40,
                  fit: BoxFit.contain,
                  errorBuilder: (context, error, stackTrace) =>
                      const Icon(Icons.image_not_supported_outlined),
                ),
              ),
            ),
          IconButton(
            tooltip: 'Logout',
            onPressed: _logout,
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: SafeArea(child: pages[selectedTab]),
      bottomNavigationBar: NavigationBar(
        selectedIndex: selectedTab,
        onDestinationSelected: (value) => setState(() => tab = value),
        destinations: [
          const NavigationDestination(
            icon: Icon(Icons.dashboard_outlined),
            selectedIcon: Icon(Icons.dashboard),
            label: 'Home',
          ),
          const NavigationDestination(
            icon: Icon(Icons.chat_bubble_outline),
            selectedIcon: Icon(Icons.chat_bubble),
            label: 'Chat',
          ),
          const NavigationDestination(
            icon: Icon(Icons.storefront_outlined),
            selectedIcon: Icon(Icons.storefront),
            label: 'Laden',
          ),
          const NavigationDestination(
            icon: Icon(Icons.settings_outlined),
            selectedIcon: Icon(Icons.settings),
            label: 'Profil',
          ),
          if (isAdmin)
            const NavigationDestination(
              icon: Icon(Icons.admin_panel_settings_outlined),
              selectedIcon: Icon(Icons.admin_panel_settings),
              label: 'Admin',
            ),
        ],
      ),
    );
  }
}

enum AuthMode { login, invite, setup }

class LoginScreen extends StatefulWidget {
  const LoginScreen({
    required this.onLogin,
    required this.onInvite,
    required this.onSetupAdmin,
    this.error,
    super.key,
  });

  final Future<void> Function(String username, String password) onLogin;
  final Future<void> Function(
    String code,
    String username,
    String password,
    String passwordConfirm,
  ) onInvite;
  final Future<void> Function(
    String username,
    String password,
    String passwordConfirm,
  ) onSetupAdmin;
  final String? error;

  @override
  State<LoginScreen> createState() => _LoginScreenState();
}

class _LoginScreenState extends State<LoginScreen> {
  final username = TextEditingController();
  final password = TextEditingController();
  final passwordConfirm = TextEditingController();
  final inviteCode = TextEditingController();
  AuthMode mode = AuthMode.login;
  bool busy = false;
  String? error;

  @override
  void dispose() {
    username.dispose();
    password.dispose();
    passwordConfirm.dispose();
    inviteCode.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    final title = switch (mode) {
      AuthMode.login => 'Einloggen',
      AuthMode.invite => 'Mit Code registrieren',
      AuthMode.setup => 'Admin festlegen',
    };
    final action = switch (mode) {
      AuthMode.login => 'Login',
      AuthMode.invite => 'Konto erstellen',
      AuthMode.setup => 'Admin festlegen',
    };
    final icon = switch (mode) {
      AuthMode.login => Icons.login,
      AuthMode.invite => Icons.card_giftcard,
      AuthMode.setup => Icons.admin_panel_settings,
    };

    return Scaffold(
      appBar: AppBar(title: const Text('lerngruppen finder')),
      body: Center(
        child: ConstrainedBox(
          constraints: const BoxConstraints(maxWidth: 420),
          child: ListView(
            padding: const EdgeInsets.all(20),
            shrinkWrap: true,
            children: [
              Text(title, style: Theme.of(context).textTheme.headlineMedium),
              const SizedBox(height: 20),
              SegmentedButton<AuthMode>(
                segments: const [
                  ButtonSegment(
                    value: AuthMode.login,
                    icon: Icon(Icons.login),
                    label: Text('Login'),
                  ),
                  ButtonSegment(
                    value: AuthMode.invite,
                    icon: Icon(Icons.card_giftcard),
                    label: Text('Code'),
                  ),
                  ButtonSegment(
                    value: AuthMode.setup,
                    icon: Icon(Icons.admin_panel_settings),
                    label: Text('Admin'),
                  ),
                ],
                selected: {mode},
                onSelectionChanged: busy
                    ? null
                    : (set) => setState(() {
                          mode = set.first;
                          error = null;
                        }),
              ),
              if (mode == AuthMode.setup) ...[
                const SizedBox(height: 12),
                Text(
                  'Nur möglich, wenn kein Admin-Konto existiert.',
                  style: Theme.of(context).textTheme.bodySmall,
                ),
              ],
              if (mode == AuthMode.invite) ...[
                const SizedBox(height: 12),
                TextField(
                  controller: inviteCode,
                  textInputAction: TextInputAction.next,
                  decoration: const InputDecoration(labelText: 'Einladungscode'),
                ),
              ],
              const SizedBox(height: 12),
              TextField(
                controller: username,
                textInputAction: TextInputAction.next,
                decoration: const InputDecoration(labelText: 'Benutzername'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: password,
                obscureText: true,
                onSubmitted: (_) => _submit(),
                decoration: const InputDecoration(labelText: 'Passwort'),
              ),
              if (mode != AuthMode.login) ...[
                const SizedBox(height: 12),
                TextField(
                  controller: passwordConfirm,
                  obscureText: true,
                  onSubmitted: (_) => _submit(),
                  decoration: const InputDecoration(
                    labelText: 'Passwort bestätigen',
                  ),
                ),
              ],
              const SizedBox(height: 16),
              FilledButton.icon(
                onPressed: busy ? null : _submit,
                icon: busy
                    ? const SizedBox(
                        width: 18,
                        height: 18,
                        child: CircularProgressIndicator(strokeWidth: 2),
                      )
                    : Icon(icon),
                label: Text(action),
              ),
              if (error != null || widget.error != null) ...[
                const SizedBox(height: 12),
                Text(
                  error ?? widget.error!,
                  style: TextStyle(color: Theme.of(context).colorScheme.error),
                ),
              ],
              const SizedBox(height: 16),
              Text(
                'API: $apiBaseUrl',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
          ),
        ),
      ),
    );
  }

  Future<void> _submit() async {
    final usernameText = username.text.trim();
    final passwordText = password.text;
    final passwordConfirmText = passwordConfirm.text;
    final inviteCodeText = inviteCode.text.trim();

    if (passwordText.length < 6) {
      setState(() => error = 'Passwort zu kurz.');
      return;
    }

    setState(() {
      busy = true;
      error = null;
    });
    try {
      if (mode == AuthMode.login) {
        await widget.onLogin(usernameText, passwordText);
      } else if (mode == AuthMode.invite) {
        await widget.onInvite(
          inviteCodeText,
          usernameText,
          passwordText,
          passwordConfirmText,
        );
      } else {
        await widget.onSetupAdmin(
          usernameText,
          passwordText,
          passwordConfirmText,
        );
      }
    } catch (ex) {
      setState(() => error = friendlyError(ex));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }
}

class DashboardScreen extends StatelessWidget {
  const DashboardScreen({
    required this.user,
    required this.onOpenChat,
    required this.onOpenShop,
    this.onOpenAdmin,
    super.key,
  });

  final UserProfile user;
  final VoidCallback onOpenChat;
  final VoidCallback onOpenShop;
  final VoidCallback? onOpenAdmin;

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('Hallo, ${user.username}', style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 16),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: [
            LevelChip(label: 'Deutsch', value: user.levelGerman),
            LevelChip(label: 'Mathe', value: user.levelMath),
            LevelChip(label: 'Englisch', value: user.levelEnglish),
          ],
        ),
        const SizedBox(height: 20),
        InfoCard(
          icon: Icons.chat_bubble_outline,
          title: 'Fachchat',
          text: 'Noob und Mittel können schreiben, sobald ein Pro im Fachraum ist.',
          onTap: onOpenChat,
        ),
        const SizedBox(height: 12),
        InfoCard(
          icon: Icons.storefront_outlined,
          title: 'Laden',
          text: 'Punkte einsehen und aktive Angebote kaufen.',
          onTap: onOpenShop,
        ),
        if (onOpenAdmin != null) ...[
          const SizedBox(height: 12),
          InfoCard(
            icon: Icons.admin_panel_settings_outlined,
            title: 'Administration',
            text: 'Nutzer, Einladungscodes, Chats, Bewertungen und Laden verwalten.',
            onTap: onOpenAdmin!,
          ),
        ],
      ],
    );
  }
}

class LevelChip extends StatelessWidget {
  const LevelChip({required this.label, required this.value, super.key});

  final String label;
  final String value;

  @override
  Widget build(BuildContext context) {
    return Chip(
      avatar: const Icon(Icons.school, size: 18),
      label: Text('$label: ${levelLabel(value)}'),
    );
  }
}

class InfoCard extends StatelessWidget {
  const InfoCard({
    required this.icon,
    required this.title,
    required this.text,
    required this.onTap,
    super.key,
  });

  final IconData icon;
  final String title;
  final String text;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return Card(
      child: ListTile(
        onTap: onTap,
        leading: Icon(icon),
        title: Text(title),
        subtitle: Text(text),
        trailing: const Icon(Icons.chevron_right),
      ),
    );
  }
}

class ChatScreen extends StatefulWidget {
  const ChatScreen({required this.api, required this.user, super.key});

  final ApiClient api;
  final UserProfile user;

  @override
  State<ChatScreen> createState() => _ChatScreenState();
}

class _ChatScreenState extends State<ChatScreen> {
  List<dynamic> rooms = const [];
  List<dynamic> messages = const [];
  String? subject;
  String? subjectLabel;
  String? error;
  int since = 0;
  Timer? timer;
  final input = TextEditingController();

  @override
  void initState() {
    super.initState();
    _loadRooms();
    timer = Timer.periodic(const Duration(seconds: 3), (_) {
      if (subject == null) {
        _loadRooms(silent: true);
      } else {
        _loadMessages(silent: true);
      }
    });
  }

  @override
  void dispose() {
    timer?.cancel();
    input.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    if (subject != null) return _chatPanel(context);
    return RefreshIndicator(
      onRefresh: _loadRooms,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Fächer-Chat', style: Theme.of(context).textTheme.headlineSmall),
          if (error != null) ErrorBanner(error!),
          const SizedBox(height: 12),
          for (final room in rooms) _roomCard(room as Map<String, dynamic>),
        ],
      ),
    );
  }

  Widget _roomCard(Map<String, dynamic> room) {
    final members = (room['members'] as List? ?? const []);
    final canJoin = room['can_join'] == true;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(room['label'].toString(), style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 6),
              Text(
                '${room['count_non_pro']} / ${room['max']} ohne Pro, '
                '${room['count_pro']} Pro online',
              ),
              if (members.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Text(
                    members
                        .map((m) => '${m['username']} (${levelLabel(m['level'])})')
                        .join(', '),
                  ),
                ),
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: canJoin ? () => _join(room) : null,
                icon: const Icon(Icons.meeting_room),
                label: Text(room['you_in'] == true ? 'Fortsetzen' : 'Beitreten'),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _chatPanel(BuildContext context) {
    return Column(
      children: [
        Material(
          color: Theme.of(context).colorScheme.surface,
          child: ListTile(
            leading: IconButton(
              tooltip: 'Zurück',
              onPressed: _leave,
              icon: const Icon(Icons.arrow_back),
            ),
            title: Text(subjectLabel ?? 'Chat'),
            subtitle: error == null ? null : Text(error!),
          ),
        ),
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: messages.length,
            itemBuilder: (context, index) {
              final msg = messages[index] as Map<String, dynamic>;
              final own = msg['user_id'] == widget.user.userId;
              return Align(
                alignment: own ? Alignment.centerRight : Alignment.centerLeft,
                child: Card(
                  color: own ? Theme.of(context).colorScheme.primaryContainer : null,
                  child: Padding(
                    padding: const EdgeInsets.all(10),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Text(
                          '${msg['username']} · ${msg['created_at']}',
                          style: Theme.of(context).textTheme.labelSmall,
                        ),
                        const SizedBox(height: 4),
                        Text(msg['body']?.toString() ?? ''),
                      ],
                    ),
                  ),
                ),
              );
            },
          ),
        ),
        SafeArea(
          child: Padding(
            padding: const EdgeInsets.fromLTRB(12, 8, 12, 12),
            child: Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: input,
                    maxLength: 500,
                    decoration: const InputDecoration(
                      counterText: '',
                      hintText: 'Nachricht schreiben',
                    ),
                    onSubmitted: (_) => _send(),
                  ),
                ),
                const SizedBox(width: 8),
                IconButton.filled(
                  tooltip: 'Senden',
                  onPressed: _send,
                  icon: const Icon(Icons.send),
                ),
              ],
            ),
          ),
        ),
      ],
    );
  }

  Future<void> _loadRooms({bool silent = false}) async {
    try {
      final data = await widget.api.getJson('/api/chat/rooms');
      setState(() {
        rooms = data['rooms'] as List? ?? const [];
        if (!silent) error = null;
      });
    } catch (ex) {
      if (!silent) setState(() => error = ex.toString());
    }
  }

  Future<void> _join(Map<String, dynamic> room) async {
    try {
      await widget.api.postJson('/api/chat/join', {'subject': room['subject']});
      setState(() {
        subject = room['subject'].toString();
        subjectLabel = room['label'].toString();
        messages = const [];
        since = 0;
        error = null;
      });
      await _loadMessages();
    } catch (ex) {
      setState(() => error = ex.toString());
    }
  }

  Future<void> _leave() async {
    final leaving = subject;
    setState(() {
      subject = null;
      subjectLabel = null;
      messages = const [];
      since = 0;
    });
    if (leaving != null) {
      try {
        await widget.api.postJson('/api/chat/leave', {'subject': leaving});
      } catch (_) {}
    }
    await _loadRooms(silent: true);
  }

  Future<void> _loadMessages({bool silent = false}) async {
    final active = subject;
    if (active == null) return;
    try {
      final data = await widget.api.getJson('/api/chat/messages', {
        'subject': active,
        'since': since.toString(),
      });
      final next = data['messages'] as List? ?? const [];
      setState(() {
        messages = [...messages, ...next];
        for (final item in next) {
          final id = (item as Map<String, dynamic>)['id'] as int;
          if (id > since) since = id;
        }
        if (!silent) error = null;
      });
    } catch (ex) {
      if (!silent) setState(() => error = ex.toString());
    }
  }

  Future<void> _send() async {
    final active = subject;
    final body = input.text.trim();
    if (active == null || body.isEmpty) return;
    input.clear();
    try {
      await widget.api.postJson('/api/chat/send', {
        'subject': active,
        'body': body,
      });
      await _loadMessages(silent: true);
    } catch (ex) {
      setState(() => error = ex.toString());
    }
  }
}

class ShopScreen extends StatefulWidget {
  const ShopScreen({required this.api, super.key});

  final ApiClient api;

  @override
  State<ShopScreen> createState() => _ShopScreenState();
}

class _ShopScreenState extends State<ShopScreen> {
  List<dynamic> items = const [];
  int points = 0;
  String? error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Text('Laden', style: Theme.of(context).textTheme.headlineSmall),
          const SizedBox(height: 8),
          Text('Punkte: $points'),
          if (error != null) ErrorBanner(error!),
          const SizedBox(height: 12),
          for (final item in items) _shopItem(item as Map<String, dynamic>),
        ],
      ),
    );
  }

  Widget _shopItem(Map<String, dynamic> item) {
    final cost = item['points_price'] as int? ?? 0;
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Card(
        child: ListTile(
          title: Text(item['title']?.toString() ?? ''),
          subtitle: Text(item['description']?.toString() ?? ''),
          trailing: cost > 0
              ? FilledButton(
                  onPressed: points >= cost ? () => _buy(item) : null,
                  child: Text('$cost P'),
                )
              : const Icon(Icons.info_outline),
        ),
      ),
    );
  }

  Future<void> _load() async {
    try {
      final data = await widget.api.getJson('/api/shop');
      setState(() {
        items = data['items'] as List? ?? const [];
        points = data['points_balance'] as int? ?? 0;
        error = null;
      });
    } catch (ex) {
      setState(() => error = ex.toString());
    }
  }

  Future<void> _buy(Map<String, dynamic> item) async {
    try {
      final data = await widget.api.postJson('/api/shop/purchase', {
        'item_id': item['id'],
      });
      setState(() {
        points = data['points_balance'] as int? ?? points;
        error = data['mail_notice']?.toString();
      });
    } catch (ex) {
      setState(() => error = ex.toString());
    }
  }
}

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({
    required this.api,
    required this.user,
    required this.onSaved,
    super.key,
  });

  final ApiClient api;
  final UserProfile user;
  final Future<void> Function() onSaved;

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  late String german;
  late String math;
  late String english;
  late final TextEditingController email;
  late final TextEditingController currentPassword;
  late final TextEditingController newPassword;
  late final TextEditingController newPasswordConfirm;
  late bool notify;
  bool busy = false;
  String? status;

  @override
  void initState() {
    super.initState();
    german = widget.user.levelGerman;
    math = widget.user.levelMath;
    english = widget.user.levelEnglish;
    email = TextEditingController(text: widget.user.contactEmail);
    currentPassword = TextEditingController();
    newPassword = TextEditingController();
    newPasswordConfirm = TextEditingController();
    notify = widget.user.notifyLadenEmail;
  }

  @override
  void dispose() {
    email.dispose();
    currentPassword.dispose();
    newPassword.dispose();
    newPasswordConfirm.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('Profil', style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 16),
        LevelSelector(
          label: 'Deutsch',
          value: german,
          onChanged: (v) => setState(() => german = v),
        ),
        LevelSelector(
          label: 'Mathe',
          value: math,
          onChanged: (v) => setState(() => math = v),
        ),
        LevelSelector(
          label: 'Englisch',
          value: english,
          onChanged: (v) => setState(() => english = v),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: email,
          keyboardType: TextInputType.emailAddress,
          decoration: const InputDecoration(labelText: 'E-Mail-Adresse'),
        ),
        SwitchListTile(
          contentPadding: EdgeInsets.zero,
          value: notify,
          onChanged: (value) => setState(() => notify = value),
          title: const Text('Bei Laden-Käufen per E-Mail informieren'),
        ),
        const SizedBox(height: 16),
        Text('Passwort ändern', style: Theme.of(context).textTheme.titleMedium),
        const SizedBox(height: 12),
        TextField(
          controller: currentPassword,
          obscureText: true,
          decoration: const InputDecoration(labelText: 'Aktuelles Passwort'),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: newPassword,
          obscureText: true,
          decoration: const InputDecoration(labelText: 'Neues Passwort'),
        ),
        const SizedBox(height: 12),
        TextField(
          controller: newPasswordConfirm,
          obscureText: true,
          decoration: const InputDecoration(
            labelText: 'Neues Passwort bestätigen',
          ),
        ),
        const SizedBox(height: 8),
        FilledButton.icon(
          onPressed: busy ? null : _save,
          icon: const Icon(Icons.save),
          label: const Text('Speichern'),
        ),
        if (status != null) ...[
          const SizedBox(height: 12),
          Text(status!),
        ],
      ],
    );
  }

  Future<void> _save() async {
    final currentPasswordText = currentPassword.text;
    final newPasswordText = newPassword.text;
    final newPasswordConfirmText = newPasswordConfirm.text;
    final wantsPasswordChange =
        currentPasswordText.isNotEmpty ||
        newPasswordText.isNotEmpty ||
        newPasswordConfirmText.isNotEmpty;

    if (wantsPasswordChange) {
      if (currentPasswordText.isEmpty ||
          newPasswordText.isEmpty ||
          newPasswordConfirmText.isEmpty) {
        setState(() => status = 'Bitte alle Passwortfelder ausfüllen.');
        return;
      }
      if (newPasswordText.length < 6) {
        setState(() => status = 'Passwort zu kurz.');
        return;
      }
      if (newPasswordText != newPasswordConfirmText) {
        setState(() => status = 'Passwörter stimmen nicht überein.');
        return;
      }
    }

    setState(() {
      busy = true;
      status = null;
    });
    try {
      await widget.api.postJson('/api/profile', {
        'level_german': german,
        'level_math': math,
        'level_english': english,
        'contact_email': email.text.trim(),
        'notify_laden_email': notify,
        if (wantsPasswordChange) ...{
          'current_password': currentPasswordText,
          'new_password': newPasswordText,
          'new_password_confirm': newPasswordConfirmText,
        },
      });
      await widget.onSaved();
      if (wantsPasswordChange) {
        currentPassword.clear();
        newPassword.clear();
        newPasswordConfirm.clear();
      }
      setState(() => status = 'Gespeichert');
    } catch (ex) {
      setState(() => status = friendlyError(ex));
    } finally {
      if (mounted) setState(() => busy = false);
    }
  }
}

enum AdminSection { users, codes, chats, ratings, shop, teachers, logo }

class AdminScreen extends StatefulWidget {
  const AdminScreen({
    required this.api,
    required this.isDev,
    required this.onAppSettingsSaved,
    super.key,
  });

  final ApiClient api;
  final bool isDev;
  final Future<void> Function() onAppSettingsSaved;

  @override
  State<AdminScreen> createState() => _AdminScreenState();
}

class _AdminScreenState extends State<AdminScreen> {
  AdminSection section = AdminSection.users;
  bool loading = false;
  String? status;
  List<dynamic> users = const [];
  List<dynamic> codes = const [];
  List<dynamic> chats = const [];
  List<dynamic> ratings = const [];
  List<dynamic> shopItems = const [];
  List<dynamic> teachers = const [];
  String schoolLogoUrl = '';

  @override
  void initState() {
    super.initState();
    _load();
  }

  @override
  Widget build(BuildContext context) {
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView(
        padding: const EdgeInsets.all(16),
        children: [
          Row(
            children: [
              Expanded(
                child: Text(
                  'Administration',
                  style: Theme.of(context).textTheme.headlineSmall,
                ),
              ),
              IconButton(
                tooltip: 'Aktualisieren',
                onPressed: loading ? null : _load,
                icon: const Icon(Icons.refresh),
              ),
            ],
          ),
          const SizedBox(height: 12),
          SingleChildScrollView(
            scrollDirection: Axis.horizontal,
            child: SegmentedButton<AdminSection>(
              segments: const [
                ButtonSegment(
                  value: AdminSection.users,
                  icon: Icon(Icons.people),
                  label: Text('Nutzer'),
                ),
                ButtonSegment(
                  value: AdminSection.codes,
                  icon: Icon(Icons.vpn_key),
                  label: Text('Codes'),
                ),
                ButtonSegment(
                  value: AdminSection.chats,
                  icon: Icon(Icons.forum),
                  label: Text('Chats'),
                ),
                ButtonSegment(
                  value: AdminSection.ratings,
                  icon: Icon(Icons.star),
                  label: Text('Bewertungen'),
                ),
                ButtonSegment(
                  value: AdminSection.shop,
                  icon: Icon(Icons.storefront),
                  label: Text('Laden'),
                ),
                ButtonSegment(
                  value: AdminSection.teachers,
                  icon: Icon(Icons.alternate_email),
                  label: Text('Lehrer'),
                ),
                ButtonSegment(
                  value: AdminSection.logo,
                  icon: Icon(Icons.image_outlined),
                  label: Text('Logo'),
                ),
              ],
              selected: {section},
              onSelectionChanged: loading
                  ? null
                  : (set) {
                      setState(() {
                        section = set.first;
                        status = null;
                      });
                      _load();
                    },
            ),
          ),
          if (loading) ...[
            const SizedBox(height: 16),
            const LinearProgressIndicator(),
          ],
          if (status != null) ...[
            const SizedBox(height: 12),
            Text(status!),
          ],
          const SizedBox(height: 16),
          _sectionBody(),
        ],
      ),
    );
  }

  Widget _sectionBody() {
    return switch (section) {
      AdminSection.users => _usersBody(),
      AdminSection.codes => _codesBody(),
      AdminSection.chats => _chatsBody(),
      AdminSection.ratings => _ratingsBody(),
      AdminSection.shop => _shopBody(),
      AdminSection.teachers => _teachersBody(),
      AdminSection.logo => _logoBody(),
    };
  }

  Widget _usersBody() {
    if (users.isEmpty && !loading) return const Text('Keine Nutzer gefunden.');
    return Column(
      children: [
        for (final raw in users)
          AdminCard(
            title: raw['username']?.toString() ?? '',
            subtitle: _userSubtitle(raw as Map<String, dynamic>),
            leading: raw['role'] == 'admin'
                ? Icons.admin_panel_settings
                : Icons.person_outline,
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                IconButton(
                  tooltip: 'Passwort setzen',
                  onPressed: () => _changePassword(raw as Map<String, dynamic>),
                  icon: const Icon(Icons.password),
                ),
                if (widget.isDev)
                  IconButton(
                    tooltip: 'Rolle und Schule bearbeiten',
                    onPressed: () => _editUserAccess(raw as Map<String, dynamic>),
                    icon: const Icon(Icons.manage_accounts_outlined),
                  ),
                IconButton(
                  tooltip: raw['banned'] == true ? 'Entsperren' : 'Sperren',
                  onPressed: () => _setBanned(raw as Map<String, dynamic>),
                  icon: Icon(
                    raw['banned'] == true
                        ? Icons.lock_open
                        : Icons.block_outlined,
                  ),
                ),
              ],
            ),
          ),
      ],
    );
  }

  Widget _codesBody() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Align(
          alignment: Alignment.centerLeft,
          child: FilledButton.icon(
            onPressed: loading ? null : _createInviteCode,
            icon: const Icon(Icons.add),
            label: const Text('Code erstellen'),
          ),
        ),
        const SizedBox(height: 12),
        if (codes.isEmpty && !loading) const Text('Keine offenen Codes.'),
        for (final raw in codes)
          AdminCard(
            title: raw['code']?.toString() ?? '',
            subtitle: _codeSubtitle(raw as Map<String, dynamic>),
            leading: Icons.vpn_key_outlined,
            trailing: IconButton(
              tooltip: 'Code kopieren',
              onPressed: () => _copyCode(raw['code']?.toString() ?? ''),
              icon: const Icon(Icons.copy),
            ),
          ),
      ],
    );
  }

  Widget _chatsBody() {
    if (chats.isEmpty && !loading) return const Text('Keine Chatdaten gefunden.');
    return Column(
      children: [
        for (final raw in chats)
          AdminCard(
            title: raw['label']?.toString() ?? raw['subject']?.toString() ?? '',
            subtitle:
                '${raw['message_count'] ?? 0} Nachrichten · ${raw['rating_count'] ?? 0} Bewertungen',
            leading: Icons.forum_outlined,
            trailing: IconButton(
              tooltip: 'Fachchat löschen',
              onPressed: () => _deleteChat(raw as Map<String, dynamic>),
              icon: const Icon(Icons.delete_outline),
            ),
          ),
      ],
    );
  }

  Widget _ratingsBody() {
    if (ratings.isEmpty && !loading) return const Text('Keine Bewertungen.');
    return Column(
      children: [
        for (final raw in ratings)
          AdminCard(
            title:
                '${raw['subject_label'] ?? raw['subject']} · ${raw['username']}',
            subtitle:
                '${raw['rating']}/5 Sterne · ${raw['comment'] ?? ''}\nAdmin-Punkte: ${raw['admin_points'] ?? 0} · ${raw['admin_note'] ?? ''}',
            leading: Icons.star_outline,
            trailing: IconButton(
              tooltip: 'Admin-Punkte bearbeiten',
              onPressed: () => _editRating(raw as Map<String, dynamic>),
              icon: const Icon(Icons.edit_outlined),
            ),
          ),
      ],
    );
  }

  Widget _shopBody() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Align(
          alignment: Alignment.centerLeft,
          child: FilledButton.icon(
            onPressed: loading ? null : () => _editShopItem(),
            icon: const Icon(Icons.add),
            label: const Text('Artikel erstellen'),
          ),
        ),
        const SizedBox(height: 12),
        if (shopItems.isEmpty && !loading) const Text('Keine Ladenartikel.'),
        for (final raw in shopItems)
          AdminCard(
            title: raw['title']?.toString() ?? '',
            subtitle: _shopSubtitle(raw as Map<String, dynamic>),
            leading: Icons.local_offer_outlined,
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                IconButton(
                  tooltip: 'Bearbeiten',
                  onPressed: () => _editShopItem(raw as Map<String, dynamic>),
                  icon: const Icon(Icons.edit_outlined),
                ),
                IconButton(
                  tooltip: 'Löschen',
                  onPressed: () => _deleteShopItem(raw as Map<String, dynamic>),
                  icon: const Icon(Icons.delete_outline),
                ),
              ],
            ),
          ),
      ],
    );
  }

  Widget _teachersBody() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Align(
          alignment: Alignment.centerLeft,
          child: FilledButton.icon(
            onPressed: loading ? null : () => _editTeacher(),
            icon: const Icon(Icons.add),
            label: const Text('Kontakt erstellen'),
          ),
        ),
        const SizedBox(height: 12),
        if (teachers.isEmpty && !loading) const Text('Keine Lehrer-Kontakte.'),
        for (final raw in teachers)
          AdminCard(
            title: raw['email']?.toString() ?? '',
            subtitle: _teacherSubtitle(raw as Map<String, dynamic>),
            leading: Icons.alternate_email,
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                IconButton(
                  tooltip: 'Bearbeiten',
                  onPressed: () => _editTeacher(raw as Map<String, dynamic>),
                  icon: const Icon(Icons.edit_outlined),
                ),
                IconButton(
                  tooltip: 'Löschen',
                  onPressed: () => _deleteTeacher(raw as Map<String, dynamic>),
                  icon: const Icon(Icons.delete_outline),
                ),
              ],
            ),
          ),
      ],
    );
  }

  Widget _logoBody() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        if (schoolLogoUrl.isNotEmpty) ...[
          Align(
            alignment: Alignment.centerLeft,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: Image.network(
                schoolLogoUrl,
                width: 96,
                height: 96,
                fit: BoxFit.contain,
                errorBuilder: (context, error, stackTrace) =>
                    const Icon(Icons.image_not_supported_outlined, size: 48),
              ),
            ),
          ),
          const SizedBox(height: 12),
          SelectableText(schoolLogoUrl),
          const SizedBox(height: 12),
        ] else
          const Text('Noch kein Schul-Logo gesetzt.'),
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            FilledButton.icon(
              onPressed: loading ? null : _editLogo,
              icon: const Icon(Icons.edit_outlined),
              label: const Text('Logo-URL setzen'),
            ),
            OutlinedButton.icon(
              onPressed:
                  loading || schoolLogoUrl.isEmpty ? null : () => _saveLogo(''),
              icon: const Icon(Icons.delete_outline),
              label: const Text('Entfernen'),
            ),
          ],
        ),
      ],
    );
  }

  String _userSubtitle(Map<String, dynamic> user) {
    final parts = <String>[
      user['role']?.toString() ?? 'user',
      if ((user['school']?.toString() ?? '').isNotEmpty)
        user['school'].toString(),
      user['banned'] == true ? 'gesperrt' : 'aktiv',
    ];
    return parts.join(' · ');
  }

  String _codeSubtitle(Map<String, dynamic> code) {
    final school = code['school']?.toString() ?? '';
    final role = code['role']?.toString() ?? 'user';
    final createdAt = code['created_at']?.toString() ?? '';
    final schoolText = school.isEmpty ? 'keine Schule' : school;
    return 'Schule: $schoolText · Rolle: $role\nErstellt: $createdAt';
  }

  String _shopSubtitle(Map<String, dynamic> item) {
    final school = item['school']?.toString() ?? '';
    final target = school.isEmpty ? 'alle Schulen' : school;
    final state = item['active'] == true ? 'aktiv' : 'inaktiv';
    final description = item['description']?.toString() ?? '';
    return '${item['points_price'] ?? 0} Punkte · $state · $target\n$description';
  }

  String _teacherSubtitle(Map<String, dynamic> teacher) {
    final parts = <String>[
      if ((teacher['display_name']?.toString() ?? '').isNotEmpty)
        teacher['display_name'].toString(),
      if ((teacher['school']?.toString() ?? '').isNotEmpty)
        teacher['school'].toString(),
      teacher['active'] == true ? 'aktiv' : 'inaktiv',
    ];
    return parts.join(' · ');
  }

  Future<void> _load() async {
    setState(() {
      loading = true;
      status = null;
    });
    try {
      final data = switch (section) {
        AdminSection.users => await widget.api.getJson('/api/admin/users'),
        AdminSection.codes => await widget.api.getJson('/api/admin/invite-codes'),
        AdminSection.chats => await widget.api.getJson('/api/admin/chats'),
        AdminSection.ratings => await widget.api.getJson('/api/admin/ratings'),
        AdminSection.shop => await widget.api.getJson('/api/admin/shop'),
        AdminSection.teachers => await widget.api.getJson('/api/admin/teachers'),
        AdminSection.logo => await widget.api.getJson('/api/admin/app-settings'),
      };
      if (!mounted) return;
      setState(() {
        switch (section) {
          case AdminSection.users:
            users = data['users'] as List? ?? const [];
            break;
          case AdminSection.codes:
            codes = data['codes'] as List? ?? const [];
            break;
          case AdminSection.chats:
            chats = data['chats'] as List? ?? const [];
            break;
          case AdminSection.ratings:
            ratings = data['ratings'] as List? ?? const [];
            break;
          case AdminSection.shop:
            shopItems = data['items'] as List? ?? const [];
            break;
          case AdminSection.teachers:
            teachers = data['teachers'] as List? ?? const [];
            break;
          case AdminSection.logo:
            schoolLogoUrl = data['school_logo_url']?.toString() ?? '';
            break;
        }
      });
    } catch (ex) {
      if (mounted) setState(() => status = 'Fehler: $ex');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> _run(String success, Future<void> Function() action) async {
    setState(() {
      loading = true;
      status = null;
    });
    try {
      await action();
      await _load();
      if (mounted) setState(() => status = success);
    } catch (ex) {
      if (mounted) setState(() => status = 'Fehler: $ex');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> _changePassword(Map<String, dynamic> user) async {
    final password = await _textDialog(
      title: 'Passwort setzen',
      label: 'Neues Passwort',
      obscure: true,
    );
    if (password == null || password.isEmpty) return;
    await _run('Passwort gespeichert', () async {
      await widget.api.postJson('/api/admin/users/password', {
        'user_id': user['id'],
        'password': password,
      });
    });
  }

  Future<void> _setBanned(Map<String, dynamic> user) async {
    final ban = user['banned'] != true;
    String? message;
    if (ban) {
      message = await _textDialog(
        title: 'Nutzer sperren',
        label: 'Grund',
        initialValue: user['banned_message']?.toString() ?? '',
        maxLength: 500,
      );
      if (message == null) return;
      if (message.trim().isEmpty) {
        setState(() => status = 'Bitte einen Sperrgrund eingeben.');
        return;
      }
    } else {
      final ok = await _confirm(
        'Nutzer entsperren?',
        user['username']?.toString() ?? '',
      );
      if (!ok) return;
    }
    await _run(ban ? 'Nutzer gesperrt' : 'Nutzer entsperrt', () async {
      await widget.api.postJson('/api/admin/users/ban', {
        'user_id': user['id'],
        'ban': ban,
        if (ban) 'message': message!.trim(),
      });
    });
  }

  Future<void> _editUserAccess(Map<String, dynamic> user) async {
    final result = await _userAccessDialog(user);
    if (result == null) return;
    await _run('Nutzer gespeichert', () async {
      await widget.api.putJson('/api/admin/users/${user['id']}', result);
    });
  }

  Future<void> _createInviteCode() async {
    final result = await _inviteCodeDialog();
    if (result == null) return;
    await _run('Code erstellt', () async {
      await widget.api.postJson('/api/admin/invite-codes', result);
    });
  }

  Future<void> _copyCode(String code) async {
    if (code.isEmpty) return;
    await Clipboard.setData(ClipboardData(text: code));
    if (!mounted) return;
    ScaffoldMessenger.of(context).showSnackBar(
      const SnackBar(content: Text('Code kopiert')),
    );
  }

  Future<void> _editLogo() async {
    final value = await _textDialog(
      title: 'Schul-Logo',
      label: 'Bild-URL',
      initialValue: schoolLogoUrl,
      maxLength: 1000,
    );
    if (value == null) return;
    await _saveLogo(value.trim());
  }

  Future<void> _saveLogo(String url) async {
    await _run('Logo gespeichert', () async {
      await widget.api.postJson('/api/admin/app-settings', {
        'school_logo_url': url,
      });
    });
    await widget.onAppSettingsSaved();
  }

  Future<void> _deleteChat(Map<String, dynamic> chat) async {
    final ok = await _confirm(
      'Fachchat löschen?',
      '${chat['label']} wird inklusive Nachrichten und Bewertungen gelöscht.',
    );
    if (!ok) return;
    await _run('Chat gelöscht', () async {
      await widget.api.deleteJson(
        '/api/admin/delete_chat/${Uri.encodeComponent(chat['subject'].toString())}',
      );
    });
  }

  Future<void> _editRating(Map<String, dynamic> rating) async {
    final result = await _scoreDialog(rating);
    if (result == null) return;
    await _run('Admin-Punkte gespeichert', () async {
      await widget.api.putJson('/api/admin/subject-score', {
        'subject': rating['subject'],
        'user_id': rating['user_id'],
        'points': result.points,
        'note': result.note,
      });
    });
  }

  Future<void> _editShopItem([Map<String, dynamic>? item]) async {
    final result = await _shopDialog(item);
    if (result == null) return;
    await _run(item == null ? 'Artikel erstellt' : 'Artikel gespeichert', () async {
      if (item == null) {
        await widget.api.postJson('/api/admin/shop', result);
      } else {
        await widget.api.putJson('/api/admin/shop/${item['id']}', result);
      }
    });
  }

  Future<void> _deleteShopItem(Map<String, dynamic> item) async {
    final ok = await _confirm('Artikel löschen?', item['title']?.toString() ?? '');
    if (!ok) return;
    await _run('Artikel gelöscht', () async {
      await widget.api.deleteJson('/api/admin/shop/${item['id']}');
    });
  }

  Future<void> _editTeacher([Map<String, dynamic>? teacher]) async {
    final result = await _teacherDialog(teacher);
    if (result == null) return;
    await _run(
      teacher == null ? 'Kontakt erstellt' : 'Kontakt gespeichert',
      () async {
        if (teacher == null) {
          await widget.api.postJson('/api/admin/teachers', result);
        } else {
          await widget.api.putJson('/api/admin/teachers/${teacher['id']}', result);
        }
      },
    );
  }

  Future<void> _deleteTeacher(Map<String, dynamic> teacher) async {
    final ok = await _confirm(
      'Kontakt löschen?',
      teacher['email']?.toString() ?? '',
    );
    if (!ok) return;
    await _run('Kontakt gelöscht', () async {
      await widget.api.deleteJson('/api/admin/teachers/${teacher['id']}');
    });
  }

  Future<bool> _confirm(String title, String message) async {
    return await showDialog<bool>(
          context: context,
          builder: (context) => AlertDialog(
            title: Text(title),
            content: Text(message),
            actions: [
              TextButton(
                onPressed: () => Navigator.pop(context, false),
                child: const Text('Abbrechen'),
              ),
              FilledButton(
                onPressed: () => Navigator.pop(context, true),
                child: const Text('OK'),
              ),
            ],
          ),
        ) ??
        false;
  }

  Future<String?> _textDialog({
    required String title,
    required String label,
    String initialValue = '',
    bool obscure = false,
    int? maxLength,
  }) async {
    final controller = TextEditingController(text: initialValue);
    final result = await showDialog<String>(
      context: context,
      builder: (context) => AlertDialog(
        title: Text(title),
        content: TextField(
          controller: controller,
          obscureText: obscure,
          autofocus: true,
          maxLength: maxLength,
          maxLines: obscure ? 1 : null,
          decoration: InputDecoration(labelText: label),
          onSubmitted: (_) => Navigator.pop(context, controller.text),
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Abbrechen'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(context, controller.text),
            child: const Text('Speichern'),
          ),
        ],
      ),
    );
    controller.dispose();
    return result?.trim();
  }

  Future<ScoreEdit?> _scoreDialog(Map<String, dynamic> rating) async {
    final points = TextEditingController(
      text: (rating['admin_points'] ?? 0).toString(),
    );
    final note = TextEditingController(text: rating['admin_note']?.toString() ?? '');
    final result = await showDialog<ScoreEdit>(
      context: context,
      builder: (context) => AlertDialog(
        title: const Text('Admin-Punkte'),
        content: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            TextField(
              controller: points,
              keyboardType: TextInputType.number,
              decoration: const InputDecoration(labelText: 'Punkte'),
            ),
            const SizedBox(height: 12),
            TextField(
              controller: note,
              maxLength: 500,
              decoration: const InputDecoration(labelText: 'Notiz'),
            ),
          ],
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(context),
            child: const Text('Abbrechen'),
          ),
          FilledButton(
            onPressed: () => Navigator.pop(
              context,
              ScoreEdit(int.tryParse(points.text.trim()) ?? 0, note.text.trim()),
            ),
            child: const Text('Speichern'),
          ),
        ],
      ),
    );
    points.dispose();
    note.dispose();
    return result;
  }

  Future<Map<String, dynamic>?> _userAccessDialog(
    Map<String, dynamic> user,
  ) async {
    var role = user['role']?.toString() ?? 'user';
    final school = TextEditingController(text: user['school']?.toString() ?? '');
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: Text(user['username']?.toString() ?? 'Nutzer'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              DropdownButtonFormField<String>(
                value: role,
                decoration: const InputDecoration(labelText: 'Rolle'),
                items: const [
                  DropdownMenuItem(value: 'user', child: Text('User')),
                  DropdownMenuItem(value: 'admin', child: Text('Admin')),
                  DropdownMenuItem(value: 'dev', child: Text('Dev')),
                ],
                onChanged: (value) {
                  if (value != null) setDialogState(() => role = value);
                },
              ),
              const SizedBox(height: 12),
              TextField(
                controller: school,
                maxLength: 120,
                decoration: const InputDecoration(labelText: 'Schule'),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Abbrechen'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, {
                'role': role,
                'school': school.text.trim(),
              }),
              child: const Text('Speichern'),
            ),
          ],
        ),
      ),
    );
    school.dispose();
    return result;
  }

  Future<Map<String, dynamic>?> _inviteCodeDialog() async {
    final school = TextEditingController();
    var role = 'user';
    final roles = widget.isDev
        ? const ['user', 'admin', 'dev']
        : const ['user', 'admin'];
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Code erstellen'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: school,
                maxLength: 120,
                decoration: InputDecoration(
                  labelText: 'Schule',
                  helperText: widget.isDev
                      ? 'Leer lassen für keine Schule'
                      : 'Wird bei Admins automatisch gesetzt',
                ),
                enabled: widget.isDev,
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                value: role,
                decoration: const InputDecoration(labelText: 'Rolle'),
                items: [
                  for (final value in roles)
                    DropdownMenuItem(value: value, child: Text(value)),
                ],
                onChanged: (value) {
                  if (value != null) setDialogState(() => role = value);
                },
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Abbrechen'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, {
                'school': school.text.trim(),
                'role': role,
              }),
              child: const Text('Erstellen'),
            ),
          ],
        ),
      ),
    );
    school.dispose();
    return result;
  }

  Future<Map<String, dynamic>?> _shopDialog(Map<String, dynamic>? item) async {
    final title = TextEditingController(text: item?['title']?.toString() ?? '');
    final description = TextEditingController(
      text: item?['description']?.toString() ?? '',
    );
    final priceHint = TextEditingController(
      text: item?['price_hint']?.toString() ?? '',
    );
    final school = TextEditingController(text: item?['school']?.toString() ?? '');
    final points = TextEditingController(
      text: (item?['points_price'] ?? 0).toString(),
    );
    final sort = TextEditingController(
      text: (item?['sort_order'] ?? 0).toString(),
    );
    var active = item?['active'] != false;
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: Text(item == null ? 'Artikel erstellen' : 'Artikel bearbeiten'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: title,
                  decoration: const InputDecoration(labelText: 'Titel'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: description,
                  maxLines: 3,
                  decoration: const InputDecoration(labelText: 'Beschreibung'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: priceHint,
                  decoration: const InputDecoration(labelText: 'Preis-Hinweis'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: points,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Punktepreis'),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: school,
                  maxLength: 120,
                  decoration: const InputDecoration(
                    labelText: 'Schule',
                    helperText: 'Leer lassen für alle Schulen',
                  ),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: sort,
                  keyboardType: TextInputType.number,
                  decoration: const InputDecoration(labelText: 'Sortierung'),
                ),
                SwitchListTile(
                  contentPadding: EdgeInsets.zero,
                  value: active,
                  onChanged: (value) => setDialogState(() => active = value),
                  title: const Text('Aktiv'),
                ),
              ],
            ),
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Abbrechen'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, {
                'title': title.text.trim(),
                'description': description.text.trim(),
                'price_hint': priceHint.text.trim(),
                'points_price': int.tryParse(points.text.trim()) ?? 0,
                'school': school.text.trim(),
                'sort_order': int.tryParse(sort.text.trim()) ?? 0,
                'active': active,
              }),
              child: const Text('Speichern'),
            ),
          ],
        ),
      ),
    );
    title.dispose();
    description.dispose();
    priceHint.dispose();
    school.dispose();
    points.dispose();
    sort.dispose();
    return result;
  }

  Future<Map<String, dynamic>?> _teacherDialog(Map<String, dynamic>? teacher) async {
    final email = TextEditingController(text: teacher?['email']?.toString() ?? '');
    final name = TextEditingController(
      text: teacher?['display_name']?.toString() ?? '',
    );
    final school = TextEditingController(
      text: teacher?['school']?.toString() ?? '',
    );
    var active = teacher?['active'] != false;
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: Text(teacher == null ? 'Kontakt erstellen' : 'Kontakt bearbeiten'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              TextField(
                controller: email,
                keyboardType: TextInputType.emailAddress,
                decoration: const InputDecoration(labelText: 'E-Mail'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: name,
                decoration: const InputDecoration(labelText: 'Name'),
              ),
              const SizedBox(height: 12),
              TextField(
                controller: school,
                maxLength: 120,
                decoration: const InputDecoration(labelText: 'Schule'),
              ),
              SwitchListTile(
                contentPadding: EdgeInsets.zero,
                value: active,
                onChanged: (value) => setDialogState(() => active = value),
                title: const Text('Aktiv'),
              ),
            ],
          ),
          actions: [
            TextButton(
              onPressed: () => Navigator.pop(context),
              child: const Text('Abbrechen'),
            ),
            FilledButton(
              onPressed: () => Navigator.pop(context, {
                'email': email.text.trim(),
                'display_name': name.text.trim(),
                'school': school.text.trim(),
                'active': active,
              }),
              child: const Text('Speichern'),
            ),
          ],
        ),
      ),
    );
    email.dispose();
    name.dispose();
    school.dispose();
    return result;
  }
}

class ScoreEdit {
  const ScoreEdit(this.points, this.note);

  final int points;
  final String note;
}

class AdminCard extends StatelessWidget {
  const AdminCard({
    required this.title,
    required this.subtitle,
    required this.leading,
    this.trailing,
    super.key,
  });

  final String title;
  final String subtitle;
  final IconData leading;
  final Widget? trailing;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 10),
      child: Card(
        child: ListTile(
          leading: Icon(leading),
          title: Text(title),
          subtitle: Text(subtitle),
          trailing: trailing,
        ),
      ),
    );
  }
}

class LevelSelector extends StatelessWidget {
  const LevelSelector({
    required this.label,
    required this.value,
    required this.onChanged,
    super.key,
  });

  final String label;
  final String value;
  final ValueChanged<String> onChanged;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Column(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          Text(label, style: Theme.of(context).textTheme.titleMedium),
          const SizedBox(height: 6),
          SegmentedButton<String>(
            segments: const [
              ButtonSegment(value: 'pro', label: Text('Pro')),
              ButtonSegment(value: 'medium', label: Text('Mittel')),
              ButtonSegment(value: 'noob', label: Text('Noob')),
            ],
            selected: {value},
            onSelectionChanged: (set) => onChanged(set.first),
          ),
        ],
      ),
    );
  }
}

class ErrorBanner extends StatelessWidget {
  const ErrorBanner(this.message, {super.key});

  final String message;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.only(top: 12),
      child: Text(
        message,
        style: TextStyle(color: Theme.of(context).colorScheme.error),
      ),
    );
  }
}

String levelLabel(Object? value) {
  return switch (value?.toString()) {
    'pro' => 'Pro',
    'medium' => 'Mittel',
    _ => 'Noob',
  };
}

String friendlyError(Object ex) {
  if (ex is ApiException) {
    if (ex.message != null && ex.message!.isNotEmpty) return ex.message!;
    return switch (ex.code) {
      'shortpass' => 'Passwort zu kurz.',
      'shortuser' => 'Benutzername zu kurz.',
      'pwd_incomplete' => 'Bitte alle Passwortfelder ausfuellen.',
      'pwd_current_wrong' => 'Aktuelles Passwort stimmt nicht.',
      'ban_message_required' => 'Bitte einen Sperrgrund eingeben.',
      'ban_message_too_long' => 'Sperrgrund ist zu lang.',
      'mismatch' => 'Passwoerter stimmen nicht ueberein.',
      'taken' => 'Benutzername ist schon vergeben.',
      'invalid' => 'Login-Daten stimmen nicht.',
      'bad_invite' => 'Einladungscode ist ungueltig.',
      'bad_contact_email' => 'E-Mail-Adresse ist ungueltig.',
      'notify_no_email' => 'Bitte erst eine E-Mail-Adresse eintragen.',
      'invalid_school' => 'Schulname ist zu lang.',
      'invalid_logo_url' => 'Logo-URL ist ungueltig.',
      'invalid_role' => 'Rolle ist ungueltig.',
      'setup_done' => 'Es gibt schon ein Admin-Konto.',
      'auth' => 'Bitte neu einloggen.',
      'forbidden' => 'Dafuer hast du keine Berechtigung.',
      _ => ex.code,
    };
  }
  return ex.toString();
}
