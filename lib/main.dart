import 'dart:async';
import 'dart:convert';
import 'package:flutter/foundation.dart';
import 'package:flutter/gestures.dart';
import 'package:flutter/material.dart';
import 'package:google_sign_in/google_sign_in.dart';

import 'home_screen.dart';
import 'mails_screen.dart';
import 'events_screen.dart';
import 'meeting_screen.dart';
import 'profile_screen.dart';

class MainNavigationWrapper extends StatefulWidget {
  const MainNavigationWrapper({
    super.key,
    required this.userAccount,
    required this.onLogout,
  });

  final GoogleSignInAccount userAccount;
  final VoidCallback onLogout;

  @override
  Widget build(BuildContext context) {
    return const MaterialApp(
      title: 'Mailwise AI',
      debugShowCheckedModeBanner: false,
      home: MailwiseScreen(),
    );
  }
}

class MailwiseScreen extends StatefulWidget {
  const MailwiseScreen({super.key});

  @override
  State<MailwiseScreen> createState() => _MailwiseScreenState();
}

class _MailwiseScreenState extends State<MailwiseScreen> {
  late final WebViewController _webController;
  final FirebaseFirestore _firestore = FirebaseFirestore.instance;
  StreamSubscription<QuerySnapshot>? _firestoreSub;
  final Set<String> _processedDocIds = {};
  bool _isLoaded = false;

  @override
  void initState() {
    super.initState();
    _initEngine();
  }

  @override
  void dispose() {
    _firestoreSub?.cancel();
    super.dispose();
  }

  Future<void> _initEngine() async {
    // 1. Android background permissions
    await [
      Permission.notification,
      Permission.scheduleExactAlarm,
      Permission.ignoreBatteryOptimizations,
    ].request();

    // 2. Setup WebViewController
    _webController = WebViewController()
      ..setJavaScriptMode(JavaScriptMode.unrestricted)
      ..setBackgroundColor(const Color(0xFFF7F9FD))
      ..addJavaScriptChannel(
        'FlutterBridge',
        onMessageReceived: (JavaScriptMessage msg) {
          _handleWebBridgeMessage(msg.message);
        },
      )
      ..setNavigationDelegate(
        NavigationDelegate(
          onPageFinished: (_) {
            if (mounted) setState(() => _isLoaded = true);
          },
        ),
      );

    // 3. Load HTML
    try {
      final html = await rootBundle.loadString('assets/index.html');
      await _webController.loadHtmlString(html);
    } catch (_) {
      await _webController.loadFlutterAsset('assets/index.html');
    }

    // 4. Firestore Background Listener
    _startFirestoreListener();
  }

  void _handleWebBridgeMessage(String jsonStr) {
    try {
      final data = jsonDecode(jsonStr);
      if (data['action'] == 'schedule') {
        final int secs = data['seconds'] ?? 10;
        final String title = data['title'] ?? 'Urgent Meeting Alert';
        _scheduleAlarm(999, title, DateTime.now().add(Duration(seconds: secs)));
      } else if (data['action'] == 'stop') {
        Alarm.stopAll();
      }
    } catch (e) {
      debugPrint("Bridge error: $e");
    }
  }

  void _startFirestoreListener() {
    _firestoreSub = _firestore
        .collection('meeting_alarms')
        .snapshots()
        .listen((snapshot) {
      for (var change in snapshot.docChanges) {
        if (change.type == DocumentChangeType.added) {
          final doc = change.doc;
          if (_processedDocIds.contains(doc.id)) continue;
          _processedDocIds.add(doc.id);

          final data = doc.data() as Map<String, dynamic>?;
          if (data == null || data['is_scam'] == true) continue;

          DateTime? meetingTime;
          if (data['timestamp'] is Timestamp) {
            meetingTime = (data['timestamp'] as Timestamp).toDate();
          } else if (data['meeting_time'] is String) {
            meetingTime = DateTime.tryParse(data['meeting_time']);
          }

          if (meetingTime != null && meetingTime.isAfter(DateTime.now())) {
            _scheduleAlarm(doc.id.hashCode, data['title'] ?? 'Meeting Event', meetingTime);
          }
        }
      }
    });
  }

  Future<void> _scheduleAlarm(int id, String title, DateTime ringTime) async {
    final settings = AlarmSettings(
      id: id,
      dateTime: DateTime(
        ringTime.year,
        ringTime.month,
        ringTime.day,
        ringTime.hour,
        ringTime.minute,
        ringTime.second,
      ),
      assetAudioPath: 'assets/sample.mp3',
      loopAudio: true,
      vibrate: true,
      volumeSettings: VolumeSettings.fade(volume: 1.0, fadeDuration: const Duration(seconds: 1)),
      notificationSettings: NotificationSettings(
        title: '🔔 $title',
        body: 'Scheduled meeting time reached! Tap to open.',
        stopButton: 'Dismiss',
      ),
    );

    await Alarm.set(alarmSettings: settings);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF7F9FD),
      body: SafeArea(
        top: false,
        child: Stack(
          children: [
            WebViewWidget(
              controller: _webController,
              // Full vertical dragging to webview engine
              gestureRecognizers: {
                Factory<VerticalDragGestureRecognizer>(() => VerticalDragGestureRecognizer()),
                Factory<HorizontalDragGestureRecognizer>(() => HorizontalDragGestureRecognizer()),
              },
            ),
            if (!_isLoaded)
              const Center(
                child: CircularProgressIndicator(color: Color(0xFF4648D4)),
              ),
          ],
        ),
      ),
    );
  }
}