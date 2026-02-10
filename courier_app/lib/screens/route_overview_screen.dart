import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../repositories/courier_repository.dart';
import 'stop_detail_screen.dart';
import 'login_screen.dart';

class RouteOverviewScreen extends StatefulWidget {
  const RouteOverviewScreen({super.key});

  @override
  State<RouteOverviewScreen> createState() => _RouteOverviewScreenState();
}

class _RouteOverviewScreenState extends State<RouteOverviewScreen> {
  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) {
      context.read<CourierRepository>().fetchContext();
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(
        title: const Text('Mi ruta'),
        actions: [
          IconButton(
            icon: const Icon(Icons.refresh),
            onPressed: () => context.read<CourierRepository>().fetchContext(),
          ),
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () {
              context.read<CourierRepository>().logout();
              Navigator.of(context).pushAndRemoveUntil(
                MaterialPageRoute(builder: (_) => const LoginScreen()),
                (r) => false,
              );
            },
          ),
        ],
      ),
      body: Consumer<CourierRepository>(
        builder: (context, repo, _) {
          if (repo.error != null && (repo.lastContext == null)) {
            return Center(
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Text(repo.error!, textAlign: TextAlign.center),
                  const SizedBox(height: 16),
                  FilledButton(
                    onPressed: () => repo.fetchContext(),
                    child: const Text('Reintentar'),
                  ),
                ],
              ),
            );
          }
          final data = repo.lastContext;
          if (data == null) {
            return const Center(child: CircularProgressIndicator());
          }
          final route = data['route'] as Map<String, dynamic>?;
          final stops = data['stops'] as List<dynamic>? ?? [];
          final status = data['status'] as String? ?? '';
          final currentId = data['current_active_stop_id'];

          if (route == null || stops.isEmpty) {
            return Center(
              child: Text(
                data['status'] ?? 'No hay ruta asignada para hoy.',
                textAlign: TextAlign.center,
              ),
            );
          }

          return RefreshIndicator(
            onRefresh: () => repo.fetchContext(),
            child: ListView(
              padding: const EdgeInsets.all(16),
              children: [
                Text('Fecha: ${route['date']}', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 8),
                Text(status, style: Theme.of(context).textTheme.bodyMedium),
                const SizedBox(height: 24),
                ...stops.asMap().entries.map((e) {
                  final stop = e.value as Map<String, dynamic>;
                  final id = stop['id'] as int?;
                  final isActive = id == currentId;
                  return Card(
                    margin: const EdgeInsets.only(bottom: 8),
                    child: ListTile(
                      title: Text(
                        'Parada #${stop['sequence']} - ${stop['codigo_entrega'] ?? ''}',
                        style: TextStyle(
                          fontWeight: isActive ? FontWeight.bold : null,
                        ),
                      ),
                      subtitle: Text(
                        '${stop['state']} - ${stop['address'] ?? ''}',
                        maxLines: 2,
                        overflow: TextOverflow.ellipsis,
                      ),
                      trailing: const Icon(Icons.chevron_right),
                      onTap: id != null
                          ? () => Navigator.of(context).push(
                                MaterialPageRoute(
                                  builder: (_) => StopDetailScreen(stopId: id, stopData: stop),
                                ),
                              )
                          : null,
                    ),
                  );
                }),
              ],
            ),
          );
        },
      ),
    );
  }
}
