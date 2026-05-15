import 'dart:async';
import 'dart:convert';

import 'package:flutter/material.dart';
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
    required this.levelGerman,
    required this.levelMath,
    required this.levelEnglish,
    required this.contactEmail,
    required this.notifyLadenEmail,
  });

  factory UserProfile.fromJson(Map<String, dynamic> json) {
    return UserProfile(
      userId: json['user_id'] as int,
      username: json['username']?.toString() ?? '',
      role: json['role']?.toString() ?? 'user',
      levelGerman: json['level_german']?.toString() ?? 'noob',
      levelMath: json['level_math']?.toString() ?? 'noob',
      levelEnglish: json['level_english']?.toString() ?? 'noob',
      contactEmail: json['contact_email']?.toString() ?? '',
      notifyLadenEmail: json['notify_laden_email'] == true,
    );
  }

  final int userId;
  final String username;
  final String role;
  final String levelGerman;
  final String levelMath;
  final String levelEnglish;
  final String contactEmail;
  final bool notifyLadenEmail;

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

    final pages = [
      DashboardScreen(
        user: user!,
        onOpenChat: () => setState(() => tab = 1),
        onOpenShop: () => setState(() => tab = 2),
      ),
      ChatScreen(api: api, user: user!),
      ShopScreen(api: api),
      SettingsScreen(api: api, user: user!, onSaved: _refreshMe),
    ];

    return Scaffold(
      appBar: AppBar(
        title: const Text('lerngruppen finder'),
        actions: [
          IconButton(
            tooltip: 'Logout',
            onPressed: _logout,
            icon: const Icon(Icons.logout),
          ),
        ],
      ),
      body: SafeArea(child: pages[tab]),
      bottomNavigationBar: NavigationBar(
        selectedIndex: tab,
        onDestinationSelected: (value) => setState(() => tab = value),
        destinations: const [
          NavigationDestination(
            icon: Icon(Icons.dashboard_outlined),
            selectedIcon: Icon(Icons.dashboard),
            label: 'Home',
          ),
          NavigationDestination(
            icon: Icon(Icons.chat_bubble_outline),
            selectedIcon: Icon(Icons.chat_bubble),
            label: 'Chat',
          ),
          NavigationDestination(
            icon: Icon(Icons.storefront_outlined),
            selectedIcon: Icon(Icons.storefront),
            label: 'Laden',
          ),
          NavigationDestination(
            icon: Icon(Icons.settings_outlined),
            selectedIcon: Icon(Icons.settings),
            label: 'Profil',
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
    setState(() {
      busy = true;
      error = null;
    });
    try {
      if (mode == AuthMode.login) {
        await widget.onLogin(username.text.trim(), password.text);
      } else if (mode == AuthMode.invite) {
        await widget.onInvite(
          inviteCode.text.trim(),
          username.text.trim(),
          password.text,
          passwordConfirm.text,
        );
      } else {
        await widget.onSetupAdmin(
          username.text.trim(),
          password.text,
          passwordConfirm.text,
        );
      }
    } catch (ex) {
      setState(() => error = 'Fehler: $ex');
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
    super.key,
  });

  final UserProfile user;
  final VoidCallback onOpenChat;
  final VoidCallback onOpenShop;

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
    notify = widget.user.notifyLadenEmail;
  }

  @override
  void dispose() {
    email.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return ListView(
      padding: const EdgeInsets.all(16),
      children: [
        Text('Profil', style: Theme.of(context).textTheme.headlineSmall),
        const SizedBox(height: 16),
        LevelSelector(label: 'Deutsch', value: german, onChanged: (v) => setState(() => german = v)),
        LevelSelector(label: 'Mathe', value: math, onChanged: (v) => setState(() => math = v)),
        LevelSelector(label: 'Englisch', value: english, onChanged: (v) => setState(() => english = v)),
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
      });
      await widget.onSaved();
      setState(() => status = 'Gespeichert');
    } catch (ex) {
      setState(() => status = 'Fehler: $ex');
    } finally {
      if (mounted) setState(() => busy = false);
    }
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
