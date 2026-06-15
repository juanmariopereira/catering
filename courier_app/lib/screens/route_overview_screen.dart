import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../repositories/courier_repository.dart';
import '../services/location_service.dart';
import 'stop_detail_screen.dart';
import 'login_screen.dart';

class RouteOverviewScreen extends StatefulWidget {
  const RouteOverviewScreen({super.key});

  @override
  State<RouteOverviewScreen> createState() => _RouteOverviewScreenState();
}

class _RouteOverviewScreenState extends State<RouteOverviewScreen> {
  final LocationService _location = LocationService();

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addPostFrameCallback((_) async {
      final repo = context.read<CourierRepository>();
      await repo.fetchContext();
      await _startLocation(repo);
    });
  }

  Future<void> _startLocation(CourierRepository repo) async {
    await _location.start(repo, intervalSeconds: repo.pingSegundos);
    if (mounted) setState(() {});
  }

  @override
  void dispose() {
    _location.stop();
    super.dispose();
  }

  Future<void> _logout() async {
    await _location.stop();
    if (!mounted) return;
    context.read<CourierRepository>().logout();
    Navigator.of(context).pushAndRemoveUntil(
      MaterialPageRoute(builder: (_) => const LoginScreen()),
      (r) => false,
    );
  }

  String _distanceLabel(dynamic distanceM) {
    if (distanceM is! int) return '';
    if (distanceM < 1000) return '$distanceM m';
    return '${(distanceM / 1000).toStringAsFixed(1)} km';
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
          IconButton(icon: const Icon(Icons.logout), onPressed: _logout),
        ],
      ),
      body: Consumer<CourierRepository>(
        builder: (context, repo, _) {
          if (repo.error != null && repo.lastContext == null) {
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
          final active = data['current_active_stop'] as Map<String, dynamic>?;

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
                // Estado del GPS y check-in automático
                Wrap(
                  spacing: 8,
                  runSpacing: 4,
                  children: [
                    Chip(
                      avatar: Icon(
                        _location.isRunning ? Icons.gps_fixed : Icons.gps_off,
                        size: 18,
                        color: _location.isRunning ? Colors.green : Colors.red,
                      ),
                      label: Text(_location.statusMessage ??
                          (_location.isRunning ? 'GPS activo' : 'GPS inactivo')),
                    ),
                    Chip(
                      avatar: Icon(
                        repo.autoCheckin ? Icons.flash_on : Icons.flash_off,
                        size: 18,
                      ),
                      label: Text(repo.autoCheckin
                          ? 'Check-in automático (${repo.radioMetros} m)'
                          : 'Check-in manual'),
                    ),
                  ],
                ),
                const SizedBox(height: 12),
                Text('Fecha: ${route['date']}', style: Theme.of(context).textTheme.titleMedium),
                const SizedBox(height: 4),
                Text(status, style: Theme.of(context).textTheme.bodyMedium),
                if (active != null) ...[
                  const SizedBox(height: 12),
                  Card(
                    color: Theme.of(context).colorScheme.primaryContainer,
                    child: ListTile(
                      leading: const Icon(Icons.local_shipping),
                      title: Text('Próxima: ${active['codigo_entrega'] ?? ''}'),
                      subtitle: Text(active['address'] ?? ''),
                      trailing: Text(
                        _distanceLabel(active['distance_m']),
                        style: Theme.of(context).textTheme.titleMedium,
                      ),
                    ),
                  ),
                ],
                const Divider(height: 28),
                ...stops.asMap().entries.map((e) {
                  final stop = e.value as Map<String, dynamic>;
                  final id = stop['id'] as int?;
                  final isActive = id == currentId;
                  return Card(
                    margin: const EdgeInsets.only(bottom: 8),
                    child: ListTile(
                      title: Text(
                        'Parada #${stop['sequence']} - ${stop['codigo_entrega'] ?? ''}',
                        style: TextStyle(fontWeight: isActive ? FontWeight.bold : null),
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
