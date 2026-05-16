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
      final preview = response.body.replaceAll(RegExp(r'\s+'), ' ').trim();
      final shortPreview =
          preview.length > 80 ? '${preview.substring(0, 80)}...' : preview;
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
    required this.className,
    required this.levelGerman,
    required this.levelMath,
    required this.levelEnglish,
    required this.levelBiology,
    required this.levelPgw,
    required this.levelSpanish,
    required this.levelArt,
    required this.proVerifiedGerman,
    required this.proVerifiedMath,
    required this.proVerifiedEnglish,
    required this.proVerifiedBiology,
    required this.proVerifiedPgw,
    required this.proVerifiedSpanish,
    required this.proVerifiedArt,
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
      className: json['class_name']?.toString() ?? '',
      levelGerman: json['level_german']?.toString() ?? 'noob',
      levelMath: json['level_math']?.toString() ?? 'noob',
      levelEnglish: json['level_english']?.toString() ?? 'noob',
      levelBiology: json['level_biology']?.toString() ?? 'noob',
      levelPgw: json['level_pgw']?.toString() ?? 'noob',
      levelSpanish: json['level_spanish']?.toString() ?? 'noob',
      levelArt: json['level_art']?.toString() ?? 'noob',
      proVerifiedGerman: json['pro_verified_german'] == true,
      proVerifiedMath: json['pro_verified_math'] == true,
      proVerifiedEnglish: json['pro_verified_english'] == true,
      proVerifiedBiology: json['pro_verified_biology'] == true,
      proVerifiedPgw: json['pro_verified_pgw'] == true,
      proVerifiedSpanish: json['pro_verified_spanish'] == true,
      proVerifiedArt: json['pro_verified_art'] == true,
      contactEmail: json['contact_email']?.toString() ?? '',
      notifyLadenEmail: json['notify_laden_email'] == true,
      schoolLogoUrl: json['school_logo_url']?.toString() ?? '',
    );
  }

  final int userId;
  final String username;
  final String role;
  final String school;
  final String className;
  final String levelGerman;
  final String levelMath;
  final String levelEnglish;
  final String levelBiology;
  final String levelPgw;
  final String levelSpanish;
  final String levelArt;
  final bool proVerifiedGerman;
  final bool proVerifiedMath;
  final bool proVerifiedEnglish;
  final bool proVerifiedBiology;
  final bool proVerifiedPgw;
  final bool proVerifiedSpanish;
  final bool proVerifiedArt;
  final String contactEmail;
  final bool notifyLadenEmail;
  final String schoolLogoUrl;

  String levelFor(String subject) {
    return switch (subject) {
      'german' => levelGerman,
      'math' => levelMath,
      'english' => levelEnglish,
      'biology' => levelBiology,
      'pgw' => levelPgw,
      'spanish' => levelSpanish,
      'art' => levelArt,
      _ => 'noob',
    };
  }

  IconData? get roleIcon {
    return iconForRole(role);
  }

  bool get isStaff => role == 'admin' || role == 'dev' || role == 'teacher';
}

IconData? iconForRole(String? role) {
  return switch (role) {
    'admin' => Icons.admin_panel_settings,
    'dev' => Icons.developer_mode,
    'teacher' => Icons.school,
    _ => null,
  };
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

    final isAdmin =
        user!.role == 'admin' || user!.role == 'dev' || user!.role == 'teacher';
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
          adminRole: user!.role,
          adminSchool: user!.school,
          adminClass: user!.className,
          onAppSettingsSaved: _refreshMe,
        ),
    ];
    final selectedTab = tab < pages.length ? tab : 0;

    return Scaffold(
      appBar: AppBar(
        toolbarHeight: 72,
        title: const Text('lerngruppen finder'),
        actions: [
          if (user!.schoolLogoUrl.isNotEmpty)
            Padding(
              padding: const EdgeInsets.symmetric(vertical: 6, horizontal: 8),
              child: ClipRRect(
                borderRadius: BorderRadius.circular(6),
                child: Image.network(
                  user!.schoolLogoUrl,
                  width: 60,
                  height: 60,
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
                  decoration:
                      const InputDecoration(labelText: 'Einladungscode'),
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
        Row(
          crossAxisAlignment: CrossAxisAlignment.center,
          children: [
            Text('Hallo, ${user.username}',
                style: Theme.of(context).textTheme.headlineSmall),
            if (user.isStaff) ...[
              const SizedBox(width: 8),
              Icon(user.roleIcon,
                  size: 26, color: Theme.of(context).colorScheme.primary),
            ],
          ],
        ),
        const SizedBox(height: 16),
        Wrap(
          spacing: 10,
          runSpacing: 10,
          children: [
            LevelChip(label: 'Deutsch', value: user.levelGerman),
            LevelChip(label: 'Mathe', value: user.levelMath),
            LevelChip(label: 'Englisch', value: user.levelEnglish),
            LevelChip(label: 'Biologie', value: user.levelBiology),
            LevelChip(label: 'PGW', value: user.levelPgw),
            LevelChip(label: 'Spanisch', value: user.levelSpanish),
            LevelChip(label: 'Kunst', value: user.levelArt),
            if (user.className.isNotEmpty)
              Chip(label: Text('Klasse ${user.className}')),
          ],
        ),
        const SizedBox(height: 20),
        InfoCard(
          icon: Icons.chat_bubble_outline,
          title: 'Fachchat',
          text:
              'Noob und Mittel können schreiben, sobald ein Pro im Fachraum ist.',
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
            text:
                'Nutzer, Einladungscodes, Chats, Bewertungen und Laden verwalten.',
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
  List<dynamic> creatableRooms = const [];
  List<dynamic> messages = const [];
  Map<String, dynamic>? appointment;
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
        _loadAppointment(silent: true);
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
          if (creatableRooms.isNotEmpty) ...[
            const SizedBox(height: 12),
            Align(
              alignment: Alignment.centerLeft,
              child: FilledButton.icon(
                onPressed: _createChatRoom,
                icon: const Icon(Icons.add_comment_outlined),
                label: const Text('Chat erstellen'),
              ),
            ),
          ],
          const SizedBox(height: 12),
          if (rooms.isEmpty && creatableRooms.isEmpty)
            const Text('Aktuell ist kein Fachchat offen.'),
          for (final room in rooms) _roomCard(room as Map<String, dynamic>),
        ],
      ),
    );
  }

  Widget _roomCard(Map<String, dynamic> room) {
    final members = (room['members'] as List? ?? const []);
    final canJoin = room['can_join'] == true;
    final joinBlock = room['join_block']?.toString();
    final buttonLabel = room['you_in'] == true
        ? 'Fortsetzen'
        : joinBlock == 'started'
            ? 'Raum geschlossen'
            : 'Beitreten';
    return Padding(
      padding: const EdgeInsets.only(bottom: 12),
      child: Card(
        child: Padding(
          padding: const EdgeInsets.all(14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.start,
            children: [
              Text(room['label'].toString(),
                  style: Theme.of(context).textTheme.titleLarge),
              const SizedBox(height: 6),
              Text(
                '${room['count_non_pro']} / ${room['max']} ohne Pro, '
                '${room['count_pro']} Pro online',
              ),
              if (members.isNotEmpty)
                Padding(
                  padding: const EdgeInsets.only(top: 8),
                  child: Wrap(
                    spacing: 8,
                    runSpacing: 4,
                    children: [
                      for (final raw in members)
                        _memberLabel(raw as Map<String, dynamic>),
                    ],
                  ),
                ),
              const SizedBox(height: 12),
              FilledButton.icon(
                onPressed: canJoin ? () => _join(room) : null,
                icon: const Icon(Icons.meeting_room),
                label: Text(buttonLabel),
              ),
            ],
          ),
        ),
      ),
    );
  }

  Widget _memberLabel(Map<String, dynamic> member) {
    final verified = member['pro_verified'] == true;
    return Row(
      mainAxisSize: MainAxisSize.min,
      children: [
        Text(
          '${member['username']} (${levelLabel(member['level'])})',
          style: Theme.of(context).textTheme.bodyMedium,
        ),
        if (verified) ...[
          const SizedBox(width: 3),
          Icon(
            Icons.verified,
            size: 15,
            color: Theme.of(context).colorScheme.primary,
          ),
        ],
      ],
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
        _appointmentPanel(context),
        Expanded(
          child: ListView.builder(
            padding: const EdgeInsets.all(16),
            itemCount: messages.length,
            itemBuilder: (context, index) {
              final msg = messages[index] as Map<String, dynamic>;
              final own = msg['user_id'] == widget.user.userId;
              final role = msg['role']?.toString();
              final senderIcon =
                  iconForRole(role ?? (own ? widget.user.role : null));
              final proVerified = msg['pro_verified'] == true;
              return Align(
                alignment: own ? Alignment.centerRight : Alignment.centerLeft,
                child: Card(
                  color: own
                      ? Theme.of(context).colorScheme.primaryContainer
                      : null,
                  child: Padding(
                    padding: const EdgeInsets.all(10),
                    child: Column(
                      crossAxisAlignment: CrossAxisAlignment.start,
                      children: [
                        Row(
                          mainAxisSize: MainAxisSize.min,
                          children: [
                            Text(
                              '${msg['username']} · ${msg['created_at']}',
                              style: Theme.of(context).textTheme.labelSmall,
                            ),
                            if (senderIcon != null) ...[
                              const SizedBox(width: 6),
                              Icon(
                                senderIcon,
                                size: 16,
                                color: Theme.of(context).colorScheme.primary,
                              ),
                            ],
                            if (proVerified) ...[
                              const SizedBox(width: 6),
                              Icon(
                                Icons.verified,
                                size: 16,
                                color: Theme.of(context).colorScheme.primary,
                              ),
                            ],
                          ],
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

  Widget _appointmentPanel(BuildContext context) {
    final active = subject;
    if (active == null) return const SizedBox.shrink();
    final data = appointment;
    final appointmentText = data?['appointment']?.toString() ?? '';
    final started = data?['started'] == true;
    final ended = data?['ended'] == true;
    final yourRating = data?['your_rating'] as Map<String, dynamic>?;
    final isPro = widget.user.levelFor(active) == 'pro';
    final ratingAvg = data?['rating_avg'];
    final ratingAvgText = ratingAvg != null ? ' · Avg $ratingAvg' : '';
    return Material(
      color: Theme.of(context).colorScheme.surfaceContainerHighest,
      child: Padding(
        padding: const EdgeInsets.fromLTRB(12, 10, 12, 10),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              children: [
                const Icon(Icons.event, size: 20),
                const SizedBox(width: 8),
                Expanded(
                  child: Text(
                    appointmentText.isEmpty
                        ? 'Kein Termin gesetzt'
                        : 'Termin: $appointmentText',
                  ),
                ),
              ],
            ),
            if (ended) ...[
              const SizedBox(height: 6),
              Text(
                'Termin beendet',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ] else if (started) ...[
              const SizedBox(height: 6),
              Text(
                'Termin läuft · Raum geschlossen',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
            if (isPro && data?['rating_count'] != null) ...[
              const SizedBox(height: 6),
              Text(
                'Bewertungen: ${data?['rating_count']}$ratingAvgText',
                style: Theme.of(context).textTheme.bodySmall,
              ),
            ],
            const SizedBox(height: 8),
            Wrap(
              spacing: 8,
              runSpacing: 8,
              children: [
                if (isPro && !started && !ended)
                  OutlinedButton.icon(
                    onPressed: _setAppointment,
                    icon: const Icon(Icons.edit_calendar),
                    label: Text(
                      appointmentText.isEmpty
                          ? 'Termin setzen'
                          : 'Termin ändern',
                    ),
                  ),
                if (isPro && appointmentText.isNotEmpty && !started && !ended)
                  FilledButton.icon(
                    onPressed: _startAppointment,
                    icon: const Icon(Icons.play_arrow),
                    label: const Text('Termin starten'),
                  ),
                if (isPro && started && !ended)
                  FilledButton.icon(
                    onPressed: _endAppointment,
                    icon: const Icon(Icons.flag),
                    label: const Text('Termin beenden'),
                  ),
                if (isPro && ended)
                  FilledButton.icon(
                    onPressed: () => _rateAppointment(yourRating),
                    icon: const Icon(Icons.star),
                    label: Text(
                      yourRating == null ? 'Bewerten' : 'Bewertung ändern',
                    ),
                  ),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Future<void> _loadRooms({bool silent = false}) async {
    try {
      final data = await widget.api.getJson('/api/chat/rooms');
      setState(() {
        rooms = data['rooms'] as List? ?? const [];
        creatableRooms = data['creatable'] as List? ?? const [];
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
      await _loadAppointment();
    } catch (ex) {
      setState(() => error = friendlyError(ex));
    }
  }

  Future<void> _createChatRoom() async {
    Map<String, dynamic>? room;
    if (creatableRooms.length == 1) {
      room = creatableRooms.first as Map<String, dynamic>;
    } else {
      room = await showDialog<Map<String, dynamic>>(
        context: context,
        builder: (context) => SimpleDialog(
          title: const Text('Chat erstellen'),
          children: [
            for (final raw in creatableRooms)
              Builder(
                builder: (context) {
                  final roomItem = raw as Map<String, dynamic>;
                  return SimpleDialogOption(
                    onPressed: () => Navigator.of(context).pop(roomItem),
                    child: Text(roomItem['label'].toString()),
                  );
                },
              ),
          ],
        ),
      );
    }
    if (room == null) return;
    await _join(room);
  }

  Future<void> _leave() async {
    final leaving = subject;
    setState(() {
      subject = null;
      subjectLabel = null;
      messages = const [];
      appointment = null;
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

  Future<void> _loadAppointment({bool silent = false}) async {
    final active = subject;
    if (active == null) return;
    try {
      final data = await widget.api.getJson('/api/chat/appointment', {
        'subject': active,
      });
      setState(() {
        appointment = data;
        if (!silent) error = null;
      });
    } catch (ex) {
      if (!silent) setState(() => error = ex.toString());
    }
  }

  Future<void> _setAppointment() async {
    final active = subject;
    if (active == null) return;
    final now = DateTime.now();
    final date = await showDatePicker(
      context: context,
      initialDate: now,
      firstDate: DateTime(now.year, now.month, now.day),
      lastDate: DateTime(now.year + 2),
    );
    if (date == null) return;
    if (!mounted) return;
    final time = await showTimePicker(
      context: context,
      initialTime: TimeOfDay.fromDateTime(now.add(const Duration(hours: 1))),
    );
    if (time == null) return;
    final value =
        '${date.year}-${_two(date.month)}-${_two(date.day)} ${_two(time.hour)}:${_two(time.minute)}';
    try {
      await widget.api.postJson('/api/chat/appointment', {
        'subject': active,
        'appointment': value,
      });
      await _loadAppointment();
      await _loadRooms(silent: true);
    } catch (ex) {
      setState(() => error = friendlyError(ex));
    }
  }

  Future<void> _endAppointment() async {
    final active = subject;
    if (active == null) return;
    try {
      await widget.api.postJson('/api/chat/appointment/end', {
        'subject': active,
      });
      await _loadAppointment();
    } catch (ex) {
      setState(() => error = friendlyError(ex));
    }
  }

  Future<void> _startAppointment() async {
    final active = subject;
    if (active == null) return;
    try {
      await widget.api.postJson('/api/chat/appointment/start', {
        'subject': active,
      });
      await _loadAppointment();
      await _loadRooms(silent: true);
    } catch (ex) {
      setState(() => error = friendlyError(ex));
    }
  }

  Future<void> _rateAppointment(Map<String, dynamic>? current) async {
    final active = subject;
    if (active == null) return;
    final result = await _ratingDialog(current);
    if (result == null) return;
    if (result.rating < 4 && result.comment.trim().isEmpty) {
      setState(
          () => error = 'Bei weniger als 4 Sternen ist ein Kommentar nötig.');
      return;
    }
    try {
      await widget.api.postJson('/api/chat/appointment/rate', {
        'subject': active,
        'rating': result.rating,
        'comment': result.comment.trim(),
      });
      await _loadAppointment();
    } catch (ex) {
      setState(() => error = friendlyError(ex));
    }
  }

  Future<RatingEdit?> _ratingDialog(Map<String, dynamic>? current) async {
    var rating = int.tryParse(current?['rating']?.toString() ?? '') ?? 5;
    final comment = TextEditingController(
      text: current?['comment']?.toString() ?? '',
    );
    final result = await showDialog<RatingEdit>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Termin bewerten'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              DropdownButtonFormField<int>(
                value: rating,
                decoration: const InputDecoration(labelText: 'Bewertung'),
                items: const [
                  DropdownMenuItem(value: 5, child: Text('5 Sterne')),
                  DropdownMenuItem(value: 4, child: Text('4 Sterne')),
                  DropdownMenuItem(value: 3, child: Text('3 Sterne')),
                  DropdownMenuItem(value: 2, child: Text('2 Sterne')),
                  DropdownMenuItem(value: 1, child: Text('1 Stern')),
                ],
                onChanged: (value) {
                  if (value != null) setDialogState(() => rating = value);
                },
              ),
              const SizedBox(height: 12),
              TextField(
                controller: comment,
                maxLines: 3,
                decoration: const InputDecoration(labelText: 'Kommentar'),
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
                RatingEdit(rating, comment.text),
              ),
              child: const Text('Speichern'),
            ),
          ],
        ),
      ),
    );
    comment.dispose();
    return result;
  }
}

class RatingEdit {
  const RatingEdit(this.rating, this.comment);

  final int rating;
  final String comment;
}

String _two(int value) => value.toString().padLeft(2, '0');

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
  late String biology;
  late String pgw;
  late String spanish;
  late String art;
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
    biology = widget.user.levelBiology;
    pgw = widget.user.levelPgw;
    spanish = widget.user.levelSpanish;
    art = widget.user.levelArt;
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
        LevelSelector(
          label: 'Biologie',
          value: biology,
          onChanged: (v) => setState(() => biology = v),
        ),
        LevelSelector(
          label: 'PGW',
          value: pgw,
          onChanged: (v) => setState(() => pgw = v),
        ),
        LevelSelector(
          label: 'Spanisch',
          value: spanish,
          onChanged: (v) => setState(() => spanish = v),
        ),
        LevelSelector(
          label: 'Kunst',
          value: art,
          onChanged: (v) => setState(() => art = v),
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
    final wantsPasswordChange = currentPasswordText.isNotEmpty ||
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
        'level_biology': biology,
        'level_pgw': pgw,
        'level_spanish': spanish,
        'level_art': art,
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

enum AdminSection {
  users,
  codes,
  chats,
  ratings,
  shop,
  teachers,
  logo,
  schools
}

class AdminScreen extends StatefulWidget {
  const AdminScreen({
    required this.api,
    required this.isDev,
    required this.adminRole,
    required this.adminSchool,
    required this.adminClass,
    required this.onAppSettingsSaved,
    super.key,
  });

  final ApiClient api;
  final bool isDev;
  final String adminRole;
  final String adminSchool;
  final String adminClass;
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
  List<String> schools = const [];
  String schoolLogoUrl = '';
  String selectedLogoSchool = '';

  @override
  void initState() {
    super.initState();
    _loadSchools();
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
              segments: [
                const ButtonSegment(
                  value: AdminSection.users,
                  icon: Icon(Icons.people),
                  label: Text('Nutzer'),
                ),
                const ButtonSegment(
                  value: AdminSection.codes,
                  icon: Icon(Icons.vpn_key),
                  label: Text('Codes'),
                ),
                const ButtonSegment(
                  value: AdminSection.chats,
                  icon: Icon(Icons.forum),
                  label: Text('Chats'),
                ),
                const ButtonSegment(
                  value: AdminSection.ratings,
                  icon: Icon(Icons.star),
                  label: Text('Bewertungen'),
                ),
                const ButtonSegment(
                  value: AdminSection.shop,
                  icon: Icon(Icons.storefront),
                  label: Text('Laden'),
                ),
                const ButtonSegment(
                  value: AdminSection.teachers,
                  icon: Icon(Icons.alternate_email),
                  label: Text('Lehrer'),
                ),
                const ButtonSegment(
                  value: AdminSection.logo,
                  icon: Icon(Icons.image_outlined),
                  label: Text('Logo'),
                ),
                if (widget.isDev)
                  const ButtonSegment(
                    value: AdminSection.schools,
                    icon: Icon(Icons.school_outlined),
                    label: Text('Schulen'),
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
      AdminSection.schools => _schoolsBody(),
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
                : raw['role'] == 'teacher'
                    ? Icons.school
                    : Icons.person_outline,
            trailing: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                IconButton(
                  tooltip: 'Passwort setzen',
                  onPressed: () => _changePassword(raw),
                  icon: const Icon(Icons.password),
                ),
                if (widget.isDev)
                  IconButton(
                    tooltip: 'Rolle und Schule bearbeiten',
                    onPressed: () => _editUserAccess(raw),
                    icon: const Icon(Icons.manage_accounts_outlined),
                  ),
                if (widget.adminRole == 'admin' || widget.adminRole == 'dev')
                  IconButton(
                    tooltip: 'Klasse setzen',
                    onPressed: () => _setUserClass(raw),
                    icon: const Icon(Icons.class_outlined),
                  ),
                if (_hasProLevel(raw))
                  IconButton(
                    tooltip: 'Pros verifizieren',
                    onPressed: () => _verifyPros(raw),
                    icon: const Icon(Icons.verified_outlined),
                  ),
                IconButton(
                  tooltip: raw['banned'] == true ? 'Entsperren' : 'Sperren',
                  onPressed: () => _setBanned(raw),
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
    if (chats.isEmpty && !loading) {
      return const Text('Keine Chatdaten gefunden.');
    }
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
            subtitle: _ratingSubtitle(raw as Map<String, dynamic>),
            leading: Icons.star_outline,
            trailing: IconButton(
              tooltip: 'Admin-Punkte bearbeiten',
              onPressed: () => _editRating(raw),
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
        Wrap(
          spacing: 8,
          runSpacing: 8,
          children: [
            FilledButton.icon(
              onPressed: loading ? null : () => _editShopItem(),
              icon: const Icon(Icons.add),
              label: const Text('Artikel erstellen'),
            ),
            OutlinedButton.icon(
              onPressed: loading ? null : _bulkCreateShopItems,
              icon: const Icon(Icons.playlist_add),
              label: const Text('Massen Listung'),
            ),
          ],
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
                  onPressed: () => _editShopItem(raw),
                  icon: const Icon(Icons.edit_outlined),
                ),
                IconButton(
                  tooltip: 'Löschen',
                  onPressed: () => _deleteShopItem(raw),
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
                  onPressed: () => _editTeacher(raw),
                  icon: const Icon(Icons.edit_outlined),
                ),
                IconButton(
                  tooltip: 'Löschen',
                  onPressed: () => _deleteTeacher(raw),
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
        if (widget.isDev) ...[
          DropdownButtonFormField<String>(
            value: selectedLogoSchool.isEmpty ? null : selectedLogoSchool,
            decoration: const InputDecoration(labelText: 'Schule'),
            items: [
              for (final school in schools)
                DropdownMenuItem(value: school, child: Text(school)),
            ],
            onChanged: loading
                ? null
                : (value) {
                    setState(() {
                      selectedLogoSchool = value ?? '';
                      schoolLogoUrl = '';
                    });
                    _load();
                  },
          ),
          const SizedBox(height: 16),
        ],
        if (schoolLogoUrl.isNotEmpty) ...[
          Align(
            alignment: Alignment.centerLeft,
            child: ClipRRect(
              borderRadius: BorderRadius.circular(6),
              child: Image.network(
                schoolLogoUrl,
                width: 144,
                height: 144,
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

  Widget _schoolsBody() {
    if (!widget.isDev) return const Text('Nur fuer Devs.');
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Align(
          alignment: Alignment.centerLeft,
          child: FilledButton.icon(
            onPressed: loading ? null : _createSchool,
            icon: const Icon(Icons.add),
            label: const Text('Schule hinzufügen'),
          ),
        ),
        const SizedBox(height: 12),
        if (schools.isEmpty) const Text('Noch keine Schulen.'),
        for (final school in schools)
          AdminCard(
            title: school,
            subtitle: 'Schule',
            leading: Icons.school_outlined,
          ),
      ],
    );
  }

  String _userSubtitle(Map<String, dynamic> user) {
    final proText = _proVerificationSummary(user);
    final parts = <String>[
      user['role']?.toString() ?? 'user',
      if ((user['school']?.toString() ?? '').isNotEmpty)
        user['school'].toString(),
      if ((user['class_name']?.toString() ?? '').isNotEmpty)
        "Klasse ${user['class_name']}",
      if (proText.isNotEmpty) proText,
      user['banned'] == true ? 'gesperrt' : 'aktiv',
    ];
    return parts.join(' · ');
  }

  bool _hasProLevel(Map<String, dynamic> user) {
    return user['level_german'] == 'pro' ||
        user['level_math'] == 'pro' ||
        user['level_english'] == 'pro' ||
        user['level_biology'] == 'pro' ||
        user['level_pgw'] == 'pro' ||
        user['level_spanish'] == 'pro' ||
        user['level_art'] == 'pro';
  }

  String _proVerificationSummary(Map<String, dynamic> user) {
    final items = <String>[];
    void add(String label, String levelKey, String verifiedKey) {
      if (user[levelKey] == 'pro') {
        items.add(
            '$label ${user[verifiedKey] == true ? 'verifiziert' : 'offen'}');
      }
    }

    add('Deutsch', 'level_german', 'pro_verified_german');
    add('Mathe', 'level_math', 'pro_verified_math');
    add('Englisch', 'level_english', 'pro_verified_english');
    add('Biologie', 'level_biology', 'pro_verified_biology');
    add('PGW', 'level_pgw', 'pro_verified_pgw');
    add('Spanisch', 'level_spanish', 'pro_verified_spanish');
    add('Kunst', 'level_art', 'pro_verified_art');
    return items.join(', ');
  }

  String _codeSubtitle(Map<String, dynamic> code) {
    final school = code['school']?.toString() ?? '';
    final role = code['role']?.toString() ?? 'user';
    final createdAt = code['created_at']?.toString() ?? '';
    final schoolText = school.isEmpty ? 'keine Schule' : school;
    return 'Schule: $schoolText · Rolle: $role\nErstellt: $createdAt';
  }

  String _ratingSubtitle(Map<String, dynamic> rating) {
    final duration = _durationLabel(rating['duration_seconds']);
    final startedAt = rating['started_at']?.toString() ?? '';
    final endedAt = rating['ended_at']?.toString() ?? '';
    return '${rating['rating']}/5 Sterne · ${rating['comment'] ?? ''}'
        '${startedAt.isEmpty ? '' : '\nStart: $startedAt'}'
        '${endedAt.isEmpty ? '' : '\nEnde: $endedAt'}'
        '${duration.isEmpty ? '' : '\nDauer: $duration'}'
        '\nAdmin-Punkte: ${rating['admin_points'] ?? 0} · ${rating['admin_note'] ?? ''}';
  }

  String _durationLabel(Object? value) {
    final seconds =
        value is int ? value : int.tryParse(value?.toString() ?? '');
    if (seconds == null || seconds < 0) return '';
    final minutes = (seconds / 60).round();
    if (minutes < 60) return '$minutes Min.';
    final hours = minutes ~/ 60;
    final rest = minutes % 60;
    return rest == 0 ? '$hours Std.' : '$hours Std. $rest Min.';
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
        AdminSection.codes =>
          await widget.api.getJson('/api/admin/invite-codes'),
        AdminSection.chats => await widget.api.getJson('/api/admin/chats'),
        AdminSection.ratings => await widget.api.getJson('/api/admin/ratings'),
        AdminSection.shop => await widget.api.getJson('/api/admin/shop'),
        AdminSection.teachers =>
          await widget.api.getJson('/api/admin/teachers'),
        AdminSection.logo => await widget.api.getJson(
            '/api/admin/app-settings',
            widget.isDev && selectedLogoSchool.isNotEmpty
                ? {'school': selectedLogoSchool}
                : null,
          ),
        AdminSection.schools => await widget.api.getJson('/api/admin/schools'),
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
            selectedLogoSchool =
                data['school']?.toString() ?? selectedLogoSchool;
            break;
          case AdminSection.schools:
            schools = (data['schools'] as List? ?? const [])
                .map((item) => item.toString())
                .toList();
            break;
        }
      });
    } catch (ex) {
      if (mounted) setState(() => status = 'Fehler: $ex');
    } finally {
      if (mounted) setState(() => loading = false);
    }
  }

  Future<void> _loadSchools() async {
    try {
      final data = await widget.api.getJson('/api/admin/schools');
      if (!mounted) return;
      setState(() {
        schools = (data['schools'] as List? ?? const [])
            .map((item) => item.toString())
            .toList();
        if (widget.isDev && selectedLogoSchool.isEmpty && schools.isNotEmpty) {
          selectedLogoSchool = schools.first;
        }
      });
    } catch (_) {}
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
    await _loadSchools();
    final result = await _userAccessDialog(user);
    if (result == null) return;
    await _run('Nutzer gespeichert', () async {
      await widget.api.putJson('/api/admin/users/${user['id']}', result);
    });
  }

  Future<void> _setUserClass(Map<String, dynamic> user) async {
    final nextClass = await _textDialog(
      title: 'Klasse setzen',
      label: 'Klasse',
      initialValue: user['class_name']?.toString() ?? '',
      maxLength: 20,
    );
    if (nextClass == null) return;
    await _run('Klasse gespeichert', () async {
      await widget.api.postJson('/api/admin/users/class', {
        'user_id': user['id'],
        'class_name': nextClass.trim(),
      });
    });
  }

  Future<void> _verifyPros(Map<String, dynamic> user) async {
    final result = await _proVerificationDialog(user);
    if (result == null) return;
    await _run('Pro-Verifizierung gespeichert', () async {
      await widget.api.postJson('/api/admin/users/pro-verification', {
        'user_id': user['id'],
        ...result,
      });
    });
  }

  Future<void> _createInviteCode() async {
    await _loadSchools();
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
    await _loadSchools();
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
        if (widget.isDev) 'school': selectedLogoSchool,
      });
    });
    await widget.onAppSettingsSaved();
  }

  Future<void> _createSchool() async {
    final name = await _textDialog(
      title: 'Schule hinzufügen',
      label: 'Schulname',
      maxLength: 120,
    );
    if (name == null || name.trim().isEmpty) return;
    await _run('Schule angelegt', () async {
      await widget.api.postJson('/api/admin/schools', {'name': name.trim()});
    });
    await _loadSchools();
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

  String _defaultShopSchool() {
    final ownSchool = widget.adminSchool.trim();
    if (ownSchool.isNotEmpty) return ownSchool;
    if (!widget.isDev && schools.length == 1) return schools.first;
    return '';
  }

  void _ensureKnownSchool(String school) {
    if (school.isNotEmpty && !schools.contains(school)) {
      schools = [...schools, school];
    }
  }

  Widget _schoolControl({
    required String school,
    required ValueChanged<String> onChanged,
  }) {
    if (!widget.isDev) {
      final label = school.trim().isEmpty ? 'Keine Schule gesetzt' : school;
      return InputDecorator(
        decoration: const InputDecoration(labelText: 'Schule'),
        child: Text(label),
      );
    }
    return DropdownButtonFormField<String>(
      value: school,
      decoration: const InputDecoration(labelText: 'Schule'),
      items: [
        const DropdownMenuItem(value: '', child: Text('Keine')),
        for (final value in schools)
          DropdownMenuItem(value: value, child: Text(value)),
      ],
      onChanged: (value) {
        onChanged(value ?? '');
      },
    );
  }

  Future<void> _editShopItem([Map<String, dynamic>? item]) async {
    await _loadSchools();
    final result = await _shopDialog(item);
    if (result == null) return;
    await _run(item == null ? 'Artikel erstellt' : 'Artikel gespeichert',
        () async {
      if (item == null) {
        await widget.api.postJson('/api/admin/shop', result);
      } else {
        await widget.api.putJson('/api/admin/shop/${item['id']}', result);
      }
    });
  }

  Future<void> _bulkCreateShopItems() async {
    await _loadSchools();
    final result = await _bulkShopDialog();
    if (result == null) return;

    final titles = (result['titles'] as List<String>? ?? const [])
        .map((title) => title.trim())
        .where((title) => title.isNotEmpty)
        .toList();
    if (titles.isEmpty) {
      setState(() => status = 'Keine Artikel eingegeben.');
      return;
    }

    await _run('${titles.length} Artikel erstellt', () async {
      for (final title in titles) {
        await widget.api.postJson('/api/admin/shop', {
          'title': title,
          'description': '',
          'price_hint': result['price_hint'],
          'points_price': result['points_price'],
          'school': result['school'],
          'class_name': result['class_name'],
          'sort_order': 0,
          'active': result['active'],
        });
      }
    });
  }

  Future<void> _deleteShopItem(Map<String, dynamic> item) async {
    final ok =
        await _confirm('Artikel löschen?', item['title']?.toString() ?? '');
    if (!ok) return;
    await _run('Artikel gelöscht', () async {
      await widget.api.deleteJson('/api/admin/shop/${item['id']}');
    });
  }

  Future<void> _editTeacher([Map<String, dynamic>? teacher]) async {
    await _loadSchools();
    final result = await _teacherDialog(teacher);
    if (result == null) return;
    await _run(
      teacher == null ? 'Kontakt erstellt' : 'Kontakt gespeichert',
      () async {
        if (teacher == null) {
          await widget.api.postJson('/api/admin/teachers', result);
        } else {
          await widget.api
              .putJson('/api/admin/teachers/${teacher['id']}', result);
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
    final result = await showDialog<String>(
      context: context,
      builder: (context) => TextEntryDialog(
        title: title,
        label: label,
        initialValue: initialValue,
        obscure: obscure,
        maxLength: maxLength,
      ),
    );
    return result?.trim();
  }

  Future<ScoreEdit?> _scoreDialog(Map<String, dynamic> rating) async {
    final points = TextEditingController(
      text: (rating['admin_points'] ?? 0).toString(),
    );
    final note =
        TextEditingController(text: rating['admin_note']?.toString() ?? '');
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
              ScoreEdit(
                  int.tryParse(points.text.trim()) ?? 0, note.text.trim()),
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
    var school = user['school']?.toString() ?? '';
    if (school.isNotEmpty && !schools.contains(school)) {
      schools = [...schools, school];
    }
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
                  DropdownMenuItem(value: 'teacher', child: Text('Lehrer')),
                  DropdownMenuItem(value: 'admin', child: Text('Admin')),
                  DropdownMenuItem(value: 'dev', child: Text('Dev')),
                ],
                onChanged: (value) {
                  if (value != null) setDialogState(() => role = value);
                },
              ),
              const SizedBox(height: 12),
              DropdownButtonFormField<String>(
                value: school.isEmpty ? null : school,
                decoration: const InputDecoration(labelText: 'Schule'),
                items: [
                  for (final value in schools)
                    DropdownMenuItem(value: value, child: Text(value)),
                ],
                onChanged: (value) {
                  if (value != null) setDialogState(() => school = value);
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
                'role': role,
                'school': school,
              }),
              child: const Text('Speichern'),
            ),
          ],
        ),
      ),
    );
    return result;
  }

  Future<Map<String, dynamic>?> _proVerificationDialog(
    Map<String, dynamic> user,
  ) async {
    final username = user['username']?.toString() ?? '';
    var german = user['pro_verified_german'] == true;
    var math = user['pro_verified_math'] == true;
    var english = user['pro_verified_english'] == true;
    var biology = user['pro_verified_biology'] == true;
    var pgw = user['pro_verified_pgw'] == true;
    var spanish = user['pro_verified_spanish'] == true;
    var art = user['pro_verified_art'] == true;
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: Text('Pros verifizieren: $username'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _proVerifyTile(
                label: 'Deutsch',
                level: user['level_german'],
                value: german,
                onChanged: (value) => setDialogState(() => german = value),
              ),
              _proVerifyTile(
                label: 'Mathe',
                level: user['level_math'],
                value: math,
                onChanged: (value) => setDialogState(() => math = value),
              ),
              _proVerifyTile(
                label: 'Englisch',
                level: user['level_english'],
                value: english,
                onChanged: (value) => setDialogState(() => english = value),
              ),
              _proVerifyTile(
                label: 'Biologie',
                level: user['level_biology'],
                value: biology,
                onChanged: (value) => setDialogState(() => biology = value),
              ),
              _proVerifyTile(
                label: 'PGW',
                level: user['level_pgw'],
                value: pgw,
                onChanged: (value) => setDialogState(() => pgw = value),
              ),
              _proVerifyTile(
                label: 'Spanisch',
                level: user['level_spanish'],
                value: spanish,
                onChanged: (value) => setDialogState(() => spanish = value),
              ),
              _proVerifyTile(
                label: 'Kunst',
                level: user['level_art'],
                value: art,
                onChanged: (value) => setDialogState(() => art = value),
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
                'german': german,
                'math': math,
                'english': english,
                'biology': biology,
                'pgw': pgw,
                'spanish': spanish,
                'art': art,
              }),
              child: const Text('Speichern'),
            ),
          ],
        ),
      ),
    );
    return result;
  }

  Widget _proVerifyTile({
    required String label,
    required Object? level,
    required bool value,
    required ValueChanged<bool> onChanged,
  }) {
    final isPro = level == 'pro';
    return CheckboxListTile(
      contentPadding: EdgeInsets.zero,
      value: isPro && value,
      onChanged: isPro ? (next) => onChanged(next == true) : null,
      title: Text(label),
      subtitle: Text(isPro ? 'Pro-Level' : 'Kein Pro-Level'),
    );
  }

  Future<Map<String, dynamic>?> _inviteCodeDialog() async {
    var school = widget.isDev && schools.isNotEmpty
        ? schools.first
        : _defaultShopSchool();
    _ensureKnownSchool(school);
    var role = 'user';
    final roles = widget.isDev
        ? const ['user', 'teacher', 'admin', 'dev']
        : const ['user', 'teacher', 'admin'];
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Code erstellen'),
          content: Column(
            mainAxisSize: MainAxisSize.min,
            children: [
              _schoolControl(
                school: school,
                onChanged: (value) => setDialogState(() => school = value),
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
                'school': school,
                'role': role,
              }),
              child: const Text('Erstellen'),
            ),
          ],
        ),
      ),
    );
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
    var school = item?['school']?.toString() ??
        (item == null ? _defaultShopSchool() : '');
    _ensureKnownSchool(school);
    final className = TextEditingController(
      text: widget.adminRole == 'teacher'
          ? widget.adminClass
          : (item?['class_name']?.toString() ?? ''),
    );
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
          title:
              Text(item == null ? 'Artikel erstellen' : 'Artikel bearbeiten'),
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
                _schoolControl(
                  school: school,
                  onChanged: (value) => setDialogState(() => school = value),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: className,
                  readOnly: widget.adminRole == 'teacher',
                  decoration: const InputDecoration(
                    labelText: 'Klasse (leer = alle Klassen)',
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
                'school': school,
                'class_name': className.text.trim(),
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
    className.dispose();
    points.dispose();
    sort.dispose();
    return result;
  }

  Future<Map<String, dynamic>?> _bulkShopDialog() async {
    final titles = TextEditingController();
    final priceHint = TextEditingController();
    final points = TextEditingController(text: '0');
    var school = _defaultShopSchool();
    _ensureKnownSchool(school);
    final className = TextEditingController(
      text: widget.adminRole == 'teacher' ? widget.adminClass : '',
    );
    var active = true;
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: const Text('Massen Listung'),
          content: SingleChildScrollView(
            child: Column(
              mainAxisSize: MainAxisSize.min,
              children: [
                TextField(
                  controller: titles,
                  minLines: 6,
                  maxLines: 10,
                  decoration: const InputDecoration(
                    labelText: 'Artikel',
                    hintText: 'Ein Artikel pro Zeile',
                  ),
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
                _schoolControl(
                  school: school,
                  onChanged: (value) => setDialogState(() => school = value),
                ),
                const SizedBox(height: 12),
                TextField(
                  controller: className,
                  readOnly: widget.adminRole == 'teacher',
                  decoration: const InputDecoration(
                    labelText: 'Klasse (leer = alle Klassen)',
                  ),
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
                'titles': titles.text
                    .split(RegExp(r'\r?\n'))
                    .map((line) => line.trim())
                    .where((line) => line.isNotEmpty)
                    .toList(),
                'price_hint': priceHint.text.trim(),
                'points_price': int.tryParse(points.text.trim()) ?? 0,
                'school': school,
                'class_name': className.text.trim(),
                'active': active,
              }),
              child: const Text('Erstellen'),
            ),
          ],
        ),
      ),
    );
    titles.dispose();
    priceHint.dispose();
    className.dispose();
    points.dispose();
    return result;
  }

  Future<Map<String, dynamic>?> _teacherDialog(
      Map<String, dynamic>? teacher) async {
    final email =
        TextEditingController(text: teacher?['email']?.toString() ?? '');
    final name = TextEditingController(
      text: teacher?['display_name']?.toString() ?? '',
    );
    var school = teacher?['school']?.toString() ??
        (teacher == null ? _defaultShopSchool() : '');
    _ensureKnownSchool(school);
    var active = teacher?['active'] != false;
    final result = await showDialog<Map<String, dynamic>>(
      context: context,
      builder: (context) => StatefulBuilder(
        builder: (context, setDialogState) => AlertDialog(
          title: Text(
              teacher == null ? 'Kontakt erstellen' : 'Kontakt bearbeiten'),
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
              _schoolControl(
                school: school,
                onChanged: (value) => setDialogState(() => school = value),
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
                'school': school,
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

class TextEntryDialog extends StatefulWidget {
  const TextEntryDialog({
    required this.title,
    required this.label,
    required this.initialValue,
    required this.obscure,
    this.maxLength,
    super.key,
  });

  final String title;
  final String label;
  final String initialValue;
  final bool obscure;
  final int? maxLength;

  @override
  State<TextEntryDialog> createState() => _TextEntryDialogState();
}

class _TextEntryDialogState extends State<TextEntryDialog> {
  late final TextEditingController controller;

  @override
  void initState() {
    super.initState();
    controller = TextEditingController(text: widget.initialValue);
  }

  @override
  void dispose() {
    controller.dispose();
    super.dispose();
  }

  void _submit() {
    Navigator.of(context).pop(controller.text);
  }

  @override
  Widget build(BuildContext context) {
    return AlertDialog(
      title: Text(widget.title),
      content: TextField(
        controller: controller,
        obscureText: widget.obscure,
        autofocus: true,
        maxLength: widget.maxLength,
        maxLines: widget.obscure ? 1 : null,
        decoration: InputDecoration(labelText: widget.label),
        onSubmitted: (_) => _submit(),
      ),
      actions: [
        TextButton(
          onPressed: () => Navigator.of(context).pop(),
          child: const Text('Abbrechen'),
        ),
        FilledButton(
          onPressed: _submit,
          child: const Text('Speichern'),
        ),
      ],
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
      'invalid_datetime' => 'Bitte ein gültiges Datum wählen.',
      'permission' => 'Nur Pros können diesen Termin ändern.',
      'no_appointment' => 'Es gibt keinen Termin.',
      'not_started' => 'Der Termin wurde noch nicht gestartet.',
      'already_ended' => 'Der Termin ist schon beendet.',
      'room_closed' => 'Der Termin läuft schon. Der Raum ist geschlossen.',
      'not_ended' => 'Der Termin wurde noch nicht beendet.',
      'need_comment' => 'Bei weniger als 4 Sternen ist ein Kommentar nötig.',
      'not_in_room' => 'Du bist nicht mehr im Raum.',
      'setup_done' => 'Es gibt schon ein Admin-Konto.',
      'auth' => 'Bitte neu einloggen.',
      'forbidden' => 'Dafuer hast du keine Berechtigung.',
      _ => ex.code,
    };
  }
  return ex.toString();
}
