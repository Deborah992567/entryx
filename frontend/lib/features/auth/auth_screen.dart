/// Login / register screen.
library;

import 'package:flutter/material.dart';

import '../../app/theme.dart';
import 'auth_store.dart';

class AuthScreen extends StatefulWidget {
  const AuthScreen({super.key, required this.store});

  final AuthStore store;

  @override
  State<AuthScreen> createState() => _AuthScreenState();
}

class _AuthScreenState extends State<AuthScreen> {
  final _formKey = GlobalKey<FormState>();
  final _email = TextEditingController();
  final _password = TextEditingController();
  final _name = TextEditingController();
  bool _registerMode = false;
  bool _obscure = true;

  @override
  void dispose() {
    _email.dispose();
    _password.dispose();
    _name.dispose();
    super.dispose();
  }

  Future<void> _submit() async {
    if (!(_formKey.currentState?.validate() ?? false)) return;
    final ok = _registerMode
        ? await widget.store.register(_email.text.trim(), _password.text, _name.text.trim())
        : await widget.store.login(_email.text.trim(), _password.text);
    if (!ok && mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(
          content: Text(widget.store.error ?? 'Authentication failed'),
          backgroundColor: EntryXColors.down,
        ),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: Center(
        child: Container(
          width: 380,
          padding: const EdgeInsets.all(28),
          decoration: BoxDecoration(
            color: EntryXColors.bgRaised,
            borderRadius: BorderRadius.circular(10),
            border: Border.all(color: EntryXColors.border),
          ),
          child: ListenableBuilder(
            listenable: widget.store,
            builder: (context, _) {
              return Form(
                key: _formKey,
                child: Column(
                  mainAxisSize: MainAxisSize.min,
                  crossAxisAlignment: CrossAxisAlignment.stretch,
                  children: [
                    const Row(
                      children: [
                        Icon(Icons.trending_up, color: EntryXColors.accentBright, size: 22),
                        SizedBox(width: 8),
                        Text('ENTRYX',
                            style: TextStyle(
                                fontSize: 16,
                                fontWeight: FontWeight.w800,
                                letterSpacing: 2,
                                color: EntryXColors.text)),
                      ],
                    ),
                    const SizedBox(height: 6),
                    const Text('Professional trading terminal · local AI',
                        style: TextStyle(fontSize: 11, color: EntryXColors.textDim)),
                    const SizedBox(height: 24),
                    TextField(
                      controller: _email,
                      decoration: const InputDecoration(labelText: 'Email'),
                      keyboardType: TextInputType.emailAddress,
                      autocorrect: false,
                    ),
                    const SizedBox(height: 12),
                    if (_registerMode) ...[
                      TextField(
                        controller: _name,
                        decoration: const InputDecoration(labelText: 'Name'),
                      ),
                      const SizedBox(height: 12),
                    ],
                    TextField(
                      controller: _password,
                      decoration: InputDecoration(
                        labelText: 'Password',
                        suffixIcon: IconButton(
                          icon: Icon(_obscure ? Icons.visibility_off : Icons.visibility,
                              size: 16, color: EntryXColors.textDim),
                          onPressed: () => setState(() => _obscure = !_obscure),
                        ),
                      ),
                      obscureText: _obscure,
                      onSubmitted: (_) => _submit(),
                    ),
                    const SizedBox(height: 20),
                    FilledButton(
                      onPressed: widget.store.busy ? null : _submit,
                      style: FilledButton.styleFrom(
                        backgroundColor: EntryXColors.accent,
                        padding: const EdgeInsets.symmetric(vertical: 12),
                      ),
                      child: Text(
                        widget.store.busy
                            ? 'Working…'
                            : (_registerMode ? 'Create account' : 'Sign in'),
                      ),
                    ),
                    TextButton(
                      onPressed: widget.store.busy
                          ? null
                          : () => setState(() => _registerMode = !_registerMode),
                      child: Text(
                        _registerMode
                            ? 'Already have an account? Sign in'
                            : 'New to EntryX? Create an account',
                        style: const TextStyle(fontSize: 12, color: EntryXColors.textDim),
                      ),
                    ),
                  ],
                ),
              );
            },
          ),
        ),
      ),
    );
  }
}
