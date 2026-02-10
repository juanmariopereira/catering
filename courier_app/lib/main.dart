import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import 'services/api_service.dart';
import 'repositories/courier_repository.dart';
import 'screens/login_screen.dart';
import 'screens/route_overview_screen.dart';

void main() {
  runApp(const CourierApp());
}

class CourierApp extends StatelessWidget {
  const CourierApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MultiProvider(
      providers: [
        Provider<ApiService>(create: (_) => ApiService()),
        ChangeNotifierProxyProvider<ApiService, CourierRepository>(
          create: (context) => CourierRepository(context.read<ApiService>()),
          update: (_, api, repo) => repo ?? CourierRepository(api),
        ),
      ],
      child: MaterialApp(
        title: 'Courier',
        theme: ThemeData(
          colorScheme: ColorScheme.fromSeed(seedColor: Colors.green),
          useMaterial3: true,
        ),
        home: const AuthGate(),
      ),
    );
  }
}

class AuthGate extends StatelessWidget {
  const AuthGate({super.key});

  @override
  Widget build(BuildContext context) {
    final api = context.read<ApiService>();
    return FutureBuilder<bool>(
      future: api.hasStoredTokens(),
      builder: (context, snapshot) {
        if (snapshot.connectionState == ConnectionState.waiting) {
          return const Scaffold(body: Center(child: CircularProgressIndicator()));
        }
        if (snapshot.data == true) {
          return const RouteOverviewScreen();
        }
        return const LoginScreen();
      },
    );
  }
}
