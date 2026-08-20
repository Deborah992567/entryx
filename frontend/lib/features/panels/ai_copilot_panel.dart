/// AI Copilot panel — grounded conversational AI backed by local Ollama.
///
/// Fetches AI health on init, enables chat when the provider is reachable,
/// and anchors every response in real EntryX market data.
library;

import 'package:flutter/material.dart';
import 'package:provider/provider.dart';

import '../../app/theme.dart';
import '../../core/api_client.dart';

class AiCopilotPanel extends StatefulWidget {
  const AiCopilotPanel({super.key});

  @override
  State<AiCopilotPanel> createState() => _AiCopilotPanelState();
}

class _AiCopilotPanelState extends State<AiCopilotPanel> {
  final _controller = TextEditingController();
  final _scrollController = ScrollController();
  final _messages = <_Message>[];
  bool _aiAvailable = false;
  bool _loading = false;
  String _statusText = 'checking…';
  String _symbol = 'XAUUSD';
  String _timeframe = 'H1';

  @override
  void initState() {
    super.initState();
    _checkHealth();
  }

  @override
  void dispose() {
    _controller.dispose();
    _scrollController.dispose();
    super.dispose();
  }

  Future<void> _checkHealth() async {
    try {
      final api = context.read<ApiClient>();
      final data = await api.get('/ai/health') as Map<String, dynamic>;
      final ok = data['status'] == 'ok';
      setState(() {
        _aiAvailable = ok;
        _statusText = ok ? '${data['provider']} · ${data['default_model']}' : 'unavailable';
      });
    } catch (_) {
      setState(() {
        _aiAvailable = false;
        _statusText = 'offline';
      });
    }
  }

  Future<void> _sendMessage() async {
    final text = _controller.text.trim();
    if (text.isEmpty || _loading) return;
    _controller.clear();
    setState(() {
      _messages.add(_Message('user', text));
      _loading = true;
    });
    _scrollToBottom();
    try {
      final api = context.read<ApiClient>();
      final data = await api.post('/ai/chat', body: {
        'message': text,
        'symbol': _symbol,
        'timeframe': _timeframe,
      }) as Map<String, dynamic>;
      setState(() {
        _messages.add(_Message('assistant', data['content'] as String? ?? 'No response.'));
      });
    } catch (e) {
      setState(() {
        _messages.add(_Message('assistant', 'Error: $e'));
      });
    } finally {
      setState(() => _loading = false);
      _scrollToBottom();
    }
  }

  Future<void> _quickAnalysis(String kind) async {
    setState(() {
      _loading = true;
      _messages.add(_Message('user', '[$kind analysis]'));
    });
    _scrollToBottom();
    try {
      final api = context.read<ApiClient>();
      final data = await api.post('/ai/analyze', body: {
        'symbol': _symbol,
        'timeframe': _timeframe,
        'kind': kind,
      }) as Map<String, dynamic>;
      setState(() {
        _messages.add(_Message('assistant', data['content'] as String? ?? 'No response.'));
      });
    } catch (e) {
      setState(() {
        _messages.add(_Message('assistant', 'Error: $e'));
      });
    } finally {
      setState(() => _loading = false);
      _scrollToBottom();
    }
  }

  void _scrollToBottom() {
    WidgetsBinding.instance.addPostFrameCallback((_) {
      if (_scrollController.hasClients) {
        _scrollController.animateTo(
          _scrollController.position.maxScrollExtent,
          duration: const Duration(milliseconds: 150),
          curve: Curves.easeOut,
        );
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Column(
      children: [
        _Header(
          available: _aiAvailable,
          statusText: _statusText,
          symbol: _symbol,
          timeframe: _timeframe,
          onSymbolChanged: (s) => setState(() => _symbol = s),
          onTimeframeChanged: (t) => setState(() => _timeframe = t),
          onRefresh: _checkHealth,
        ),
        const Divider(height: 1),
        if (_aiAvailable) _QuickActions(onAnalysis: _quickAnalysis),
        if (_aiAvailable) const Divider(height: 1),
        Expanded(
          child: _messages.isEmpty
              ? _EmptyState(available: _aiAvailable)
              : ListView.builder(
                  controller: _scrollController,
                  padding: const EdgeInsets.all(8),
                  itemCount: _messages.length + (_loading ? 1 : 0),
                  itemBuilder: (context, index) {
                    if (index == _messages.length) {
                      return const _TypingIndicator();
                    }
                    return _Bubble(message: _messages[index]);
                  },
                ),
        ),
        const Divider(height: 1),
        _InputBar(
          controller: _controller,
          enabled: _aiAvailable && !_loading,
          onSend: _sendMessage,
        ),
      ],
    );
  }
}

class _Header extends StatelessWidget {
  const _Header({
    required this.available,
    required this.statusText,
    required this.symbol,
    required this.timeframe,
    required this.onSymbolChanged,
    required this.onTimeframeChanged,
    required this.onRefresh,
  });

  final bool available;
  final String statusText;
  final String symbol;
  final String timeframe;
  final ValueChanged<String> onSymbolChanged;
  final ValueChanged<String> onTimeframeChanged;
  final VoidCallback onRefresh;

  static const _symbols = ['XAUUSD', 'EURUSD', 'GBPUSD', 'USDJPY', 'BTCUSD'];
  static const _tfs = ['M1', 'M5', 'M15', 'M30', 'H1', 'H4', 'D1'];

  @override
  Widget build(BuildContext context) {
    return Container(
      height: 30,
      padding: const EdgeInsets.symmetric(horizontal: 8),
      child: Row(
        children: [
          Icon(Icons.auto_awesome, size: 14, color: available ? EntryXColors.gold : EntryXColors.textDim),
          const SizedBox(width: 6),
          const Text('AI Copilot', style: TextStyle(fontSize: 12, fontWeight: FontWeight.w600)),
          const SizedBox(width: 8),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            decoration: BoxDecoration(
              color: EntryXColors.bgRaised,
              borderRadius: BorderRadius.circular(3),
              border: Border.all(color: EntryXColors.border, width: 0.5),
            ),
            child: DropdownButton<String>(
              value: symbol,
              items: [for (final s in _symbols) DropdownMenuItem(value: s, child: Text(s, style: const TextStyle(fontSize: 10)))],
              onChanged: (v) => {if (v != null) onSymbolChanged(v)},
              underline: const SizedBox.shrink(),
              isDense: true,
              style: const TextStyle(color: EntryXColors.text, fontSize: 10),
              dropdownColor: EntryXColors.bgRaised,
              padding: EdgeInsets.zero,
            ),
          ),
          const SizedBox(width: 4),
          Container(
            padding: const EdgeInsets.symmetric(horizontal: 4),
            decoration: BoxDecoration(
              color: EntryXColors.bgRaised,
              borderRadius: BorderRadius.circular(3),
              border: Border.all(color: EntryXColors.border, width: 0.5),
            ),
            child: DropdownButton<String>(
              value: timeframe,
              items: [for (final t in _tfs) DropdownMenuItem(value: t, child: Text(t, style: const TextStyle(fontSize: 10)))],
              onChanged: (v) => {if (v != null) onTimeframeChanged(v)},
              underline: const SizedBox.shrink(),
              isDense: true,
              style: const TextStyle(color: EntryXColors.text, fontSize: 10),
              dropdownColor: EntryXColors.bgRaised,
              padding: EdgeInsets.zero,
            ),
          ),
          const Spacer(),
          GestureDetector(
            onTap: onRefresh,
            child: Row(
              mainAxisSize: MainAxisSize.min,
              children: [
                Container(
                  width: 6,
                  height: 6,
                  decoration: BoxDecoration(
                    shape: BoxShape.circle,
                    color: available ? EntryXColors.up : EntryXColors.down,
                  ),
                ),
                const SizedBox(width: 4),
                Text(statusText, style: const TextStyle(fontSize: 9, color: EntryXColors.textDim)),
              ],
            ),
          ),
        ],
      ),
    );
  }
}

class _QuickActions extends StatelessWidget {
  const _QuickActions({required this.onAnalysis});

  final ValueChanged<String> onAnalysis;

  @override
  Widget build(BuildContext context) {
    return SizedBox(
      height: 28,
      child: ListView(
        scrollDirection: Axis.horizontal,
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 4),
        children: [
          _QuickChip(label: 'Overview', onTap: () => onAnalysis('overview')),
          const SizedBox(width: 4),
          _QuickChip(label: 'Risk', onTap: () => onAnalysis('risk')),
          const SizedBox(width: 4),
          _QuickChip(label: 'Structure', onTap: () => onAnalysis('structure')),
          const SizedBox(width: 4),
          _QuickChip(label: 'SMC', onTap: () => onAnalysis('smc')),
        ],
      ),
    );
  }
}

class _QuickChip extends StatelessWidget {
  const _QuickChip({required this.label, required this.onTap});

  final String label;
  final VoidCallback onTap;

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
        decoration: BoxDecoration(
          color: EntryXColors.accentBright.withValues(alpha: 0.12),
          borderRadius: BorderRadius.circular(4),
          border: Border.all(color: EntryXColors.accentBright.withValues(alpha: 0.3), width: 0.5),
        ),
        child: Text(label, style: const TextStyle(fontSize: 10, color: EntryXColors.accentBright)),
      ),
    );
  }
}

class _EmptyState extends StatelessWidget {
  const _EmptyState({required this.available});

  final bool available;

  @override
  Widget build(BuildContext context) {
    return Center(
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          mainAxisSize: MainAxisSize.min,
          children: [
            Icon(
              Icons.auto_awesome,
              size: 28,
              color: available ? EntryXColors.gold : EntryXColors.textDim,
            ),
            const SizedBox(height: 8),
            Text(
              available ? 'Ask EntryX anything' : 'AI provider not connected',
              style: const TextStyle(fontSize: 12, color: EntryXColors.text),
            ),
            const SizedBox(height: 4),
            Text(
              available
                  ? 'All responses are grounded in real market data. Never fabricated.'
                  : 'Start Ollama locally — all AI runs on your machine.',
              textAlign: TextAlign.center,
              style: const TextStyle(fontSize: 10, color: EntryXColors.textDim),
            ),
          ],
        ),
      ),
    );
  }
}

class _TypingIndicator extends StatelessWidget {
  const _TypingIndicator();

  @override
  Widget build(BuildContext context) {
    return Align(
      alignment: Alignment.centerLeft,
      child: Container(
        margin: const EdgeInsets.symmetric(vertical: 2),
        padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 6),
        decoration: BoxDecoration(
          color: EntryXColors.bgRaised,
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: EntryXColors.border),
        ),
        child: const Row(
          mainAxisSize: MainAxisSize.min,
          children: [
            SizedBox(
              width: 12,
              height: 12,
              child: CircularProgressIndicator(strokeWidth: 1.5, color: EntryXColors.accentBright),
            ),
            SizedBox(width: 6),
            Text('thinking…', style: TextStyle(fontSize: 10, color: EntryXColors.textDim)),
          ],
        ),
      ),
    );
  }
}

class _InputBar extends StatelessWidget {
  const _InputBar({
    required this.controller,
    required this.enabled,
    required this.onSend,
  });

  final TextEditingController controller;
  final bool enabled;
  final VoidCallback onSend;

  @override
  Widget build(BuildContext context) {
    return Padding(
      padding: const EdgeInsets.all(8),
      child: Row(
        children: [
          Expanded(
            child: TextField(
              controller: controller,
              enabled: enabled,
              style: const TextStyle(fontSize: 11),
              decoration: InputDecoration(
                hintText: enabled ? 'Ask EntryX…' : 'AI offline',
                hintStyle: const TextStyle(color: EntryXColors.textDim, fontSize: 11),
                isDense: true,
                contentPadding: const EdgeInsets.symmetric(horizontal: 8, vertical: 6),
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(4),
                  borderSide: const BorderSide(color: EntryXColors.border),
                ),
                enabledBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(4),
                  borderSide: const BorderSide(color: EntryXColors.border),
                ),
                focusedBorder: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(4),
                  borderSide: const BorderSide(color: EntryXColors.accentBright),
                ),
              ),
              onSubmitted: (_) => onSend(),
            ),
          ),
          const SizedBox(width: 8),
          IconButton(
            onPressed: enabled ? onSend : null,
            icon: const Icon(Icons.send, size: 18),
            tooltip: 'Send',
            visualDensity: VisualDensity.compact,
            padding: EdgeInsets.zero,
            constraints: const BoxConstraints(minWidth: 28, minHeight: 28),
          ),
        ],
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
        constraints: BoxConstraints(maxWidth: MediaQuery.of(context).size.width * 0.85),
        decoration: BoxDecoration(
          color: isUser ? EntryXColors.accent.withValues(alpha: 0.15) : EntryXColors.bgRaised,
          borderRadius: BorderRadius.circular(6),
          border: Border.all(color: EntryXColors.border),
        ),
        child: SelectableText(message.text, style: const TextStyle(fontSize: 11)),
      ),
    );
  }
}
