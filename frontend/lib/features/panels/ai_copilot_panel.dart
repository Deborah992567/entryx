/// AI Copilot panel — grounded conversational AI.
///
/// The AI subsystem (provider abstraction, Ollama integration, feature
/// pipeline) ships in Phase 7. Until then the chat shell is present but
/// explicitly reports AI as unavailable — EntryX never fakes or calls a
/// paid service.
library;

import 'package:flutter/material.dart';

import '../../app/theme.dart';

class AiCopilotPanel extends StatefulWidget {
  const AiCopilotPanel({super.key});

  @override
  State<AiCopilotPanel> createState() => _AiCopilotPanelState();
}

class _AiCopilotPanelState extends State<AiCopilotPanel> {
  final _controller = TextEditingController();
  final _messages = <_Message>[];

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        Container(
          height: 30,
          padding: const EdgeInsets.symmetric(horizontal: 8),
          child: const Row(
            children: [
              Icon(Icons.auto_awesome, size: 14, color: EntryXColors.gold),
              SizedBox(width: 6),
              Text('AI Copilot', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
              Spacer(),
              Text('AI: unavailable', style: TextStyle(fontSize: 10, color: EntryXColors.textDim)),
            ],
          ),
        ),
        const Divider(height: 1),
        Expanded(
          child: _messages.isEmpty
              ? const _EmptyState()
              : ListView.builder(
                  padding: const EdgeInsets.all(8),
                  itemCount: _messages.length,
                  itemBuilder: (context, index) {
                    final m = _messages[index];
                    return _Bubble(message: m);
                  },
                ),
        ),
        const Divider(height: 1),
        Padding(
          padding: const EdgeInsets.all(8),
          child: Row(
            children: [
              Expanded(
                child: TextField(
                  controller: _controller,
                  enabled: false,
                  decoration: const InputDecoration(
                    hintText: 'Ask EntryX… (AI in Phase 7)',
                  ),
                  onSubmitted: (_) {},
                ),
              ),
              const SizedBox(width: 8),
              IconButton(
                onPressed: null,
                icon: const Icon(Icons.send, size: 18),
                tooltip: 'Send (requires AI provider)',
              ),
            ],
          ),
        ),
      ],
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState();

  @override
  Widget build(BuildContext context) {
    return const Center(
      child: Padding(
        padding: EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(Icons.auto_awesome, size: 28, color: EntryXColors.textDim),
            SizedBox(height: 8),
            Text(
              'AI provider not available',
              style: TextStyle(fontSize: 12, color: EntryXColors.text),
            ),
            SizedBox(height: 4),
            Text(
              'EntryX runs all AI locally (Ollama/llama.cpp). '
              'Connect a local model in Settings — Phase 7.',
              textAlign: TextAlign.center,
              style: TextStyle(fontSize: 10, color: EntryXColors.textDim),
            ),
          ],
        ),
      ),
    );
  }
}

class _Message {
  const _Message(this.role, this.text);
  final String role;
  final String text;
}

class _Bubble extends StatelessWidget {
  const _Bubble({required this.message});

  final _Message message;

  @override
  Widget build(BuildContext context) {
    final isUser = message.role == 'user';
    return Align(
      alignment: isUser ? Alignment.centerRight : Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 2),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: isUser ? EntryXColors.accent.withValues(alpha: 0.15) : EntryXColors.bgRaised,
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: EntryXColors.border),
        ),
        child: Text(message.text, style: const TextStyle(fontSize: 11)),
      ),
    );
  }
}
