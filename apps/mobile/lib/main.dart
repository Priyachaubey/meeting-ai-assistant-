import 'package:flutter/material.dart';
void main() => runApp(const ConvoPilotApp());
class ConvoPilotApp extends StatelessWidget {
  const ConvoPilotApp({super.key});
  @override
  Widget build(BuildContext context) {
    return MaterialApp(title: 'ConvoPilot AI', theme: ThemeData(useMaterial3: true, colorSchemeSeed: const Color(0xFF2DD4BF)), home: const MeetingCompanionPage());
  }
}
class MeetingCompanionPage extends StatelessWidget {
  const MeetingCompanionPage({super.key});
  @override
  Widget build(BuildContext context) {
    return Scaffold(appBar: AppBar(title: const Text('ConvoPilot AI')), body: Padding(padding: const EdgeInsets.all(16), child: Column(crossAxisAlignment: CrossAxisAlignment.stretch, children: [const Text('Mobile companion', style: TextStyle(fontSize: 28, fontWeight: FontWeight.w700)), const SizedBox(height: 12), const Text('Capture-device controls, emergency stop, transcript stream, and AI suggestions live here.'), const SizedBox(height: 24), FilledButton.icon(onPressed: () {}, icon: const Icon(Icons.mic), label: const Text('Start Meeting')), OutlinedButton.icon(onPressed: () {}, icon: const Icon(Icons.stop_circle), label: const Text('Emergency Stop'))])));
  }
}
