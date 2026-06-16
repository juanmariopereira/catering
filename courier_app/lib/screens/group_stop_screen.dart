import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../repositories/courier_repository.dart';

/// Pantalla de confirmación para un grupo de entregas (edificio, condominio, oficina).
/// Todas las entregas aparecen pre-marcadas como "entregadas". El repartidor puede
/// desmarcar las que no pudo entregar (requiere motivo). Al confirmar, el backend
/// recibe los eventos correspondientes y marca el grupo automáticamente.
class GroupStopScreen extends StatefulWidget {
  final int grupoPeId;
  final String grupoNombre;
  final String notasAcceso;
  final List<Map<String, dynamic>> stops;

  const GroupStopScreen({
    super.key,
    required this.grupoPeId,
    required this.grupoNombre,
    required this.notasAcceso,
    required this.stops,
  });

  @override
  State<GroupStopScreen> createState() => _GroupStopScreenState();
}

class _GroupStopScreenState extends State<GroupStopScreen> {
  // For each stop: true = entregada, false = no entregada
  late final Map<int, bool> _delivered;
  // Motivos para las no entregadas
  final Map<int, String> _reasons = {};
  bool _loading = false;

  @override
  void initState() {
    super.initState();
    _delivered = {
      for (final s in widget.stops)
        (s['id'] as int): _alreadyDone(s['state'] as String? ?? ''),
    };
  }

  bool _alreadyDone(String state) => state == 'DELIVERED' || state == 'FAILED';

  bool _isCorrectMode(Map<String, dynamic> stop) {
    final state = stop['state'] as String? ?? '';
    return state == 'DELIVERED' || state == 'FAILED';
  }

  Future<void> _toggleDelivered(int stopId, bool val) async {
    if (!val) {
      // Pedir motivo antes de desmarcar
      final reason = await _askReason();
      if (reason == null) return; // cancelado
      setState(() {
        _delivered[stopId] = false;
        _reasons[stopId] = reason;
      });
    } else {
      setState(() {
        _delivered[stopId] = true;
        _reasons.remove(stopId);
      });
    }
  }

  Future<String?> _askReason() {
    final controller = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Text('Motivo de no entrega'),
        content: TextField(
          controller: controller,
          autofocus: true,
          decoration: const InputDecoration(
            hintText: 'Ej: No estaba en casa, buzón lleno…',
          ),
          maxLines: 3,
        ),
        actions: [
          TextButton(
            onPressed: () => Navigator.pop(ctx),
            child: const Text('Cancelar'),
          ),
          FilledButton(
            onPressed: () {
              if (controller.text.trim().isEmpty) return;
              Navigator.pop(ctx, controller.text.trim());
            },
            child: const Text('Confirmar'),
          ),
        ],
      ),
    );
  }

  Future<void> _confirmGroup() async {
    setState(() => _loading = true);
    final repo = context.read<CourierRepository>();

    final items = widget.stops.map((s) {
      final id = s['id'] as int;
      return {
        'stopId': id,
        'delivered': _delivered[id] ?? true,
        'reason': _reasons[id],
        'state': s['state'] as String? ?? '',
      };
    }).toList();

    await repo.confirmGroup(items);

    if (mounted) {
      setState(() => _loading = false);
      Navigator.of(context).pop();
    }
  }

  Future<void> _correct(Map<String, dynamic> stop) async {
    final id = stop['id'] as int;
    final state = stop['state'] as String? ?? '';
    final repo = context.read<CourierRepository>();

    if (state == 'DELIVERED') {
      final reason = await _askReason();
      if (reason == null) return;
      setState(() => _loading = true);
      await repo.attemptCorrect(id, 'FAILED', reason: reason);
    } else if (state == 'FAILED') {
      setState(() => _loading = true);
      await repo.attemptCorrect(id, 'DELIVERED');
    }
    if (mounted) setState(() => _loading = false);
  }

  String _stateLabel(String state) {
    switch (state) {
      case 'DELIVERED':
        return 'Entregado';
      case 'FAILED':
        return 'No entregado';
      case 'ARRIVED':
        return 'En sitio';
      case 'EN_ROUTE':
        return 'En camino';
      default:
        return state;
    }
  }

  Color _stateColor(String state) {
    switch (state) {
      case 'DELIVERED':
        return Colors.green;
      case 'FAILED':
        return Colors.red;
      case 'ARRIVED':
        return Colors.orange;
      default:
        return Colors.grey;
    }
  }

  @override
  Widget build(BuildContext context) {
    final allPending = widget.stops.every((s) {
      final state = s['state'] as String? ?? '';
      return state != 'DELIVERED' && state != 'FAILED';
    });

    return Scaffold(
      appBar: AppBar(
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text(widget.grupoNombre),
            if (widget.notasAcceso.isNotEmpty)
              Text(
                widget.notasAcceso,
                style: const TextStyle(fontSize: 12),
              ),
          ],
        ),
      ),
      body: _loading
          ? const Center(child: CircularProgressIndicator())
          : Column(
              children: [
                Expanded(
                  child: ListView.builder(
                    padding: const EdgeInsets.all(16),
                    itemCount: widget.stops.length,
                    itemBuilder: (_, i) {
                      final stop = widget.stops[i];
                      final id = stop['id'] as int;
                      final state = stop['state'] as String? ?? '';
                      final address = stop['address'] as String? ?? '';
                      final codigo = stop['codigo_entrega'] as String? ?? '#$id';
                      final done = _isCorrectMode(stop);

                      if (done) {
                        // Stop ya procesado: mostrar estado + botón corregir
                        return Card(
                          margin: const EdgeInsets.only(bottom: 8),
                          child: ListTile(
                            leading: Icon(
                              state == 'DELIVERED'
                                  ? Icons.check_circle
                                  : Icons.cancel,
                              color: _stateColor(state),
                            ),
                            title: Text(codigo),
                            subtitle: Text(address, maxLines: 1, overflow: TextOverflow.ellipsis),
                            trailing: TextButton(
                              onPressed: () => _correct(stop),
                              child: Text(_stateLabel(
                                  state == 'DELIVERED' ? 'FAILED' : 'DELIVERED')),
                            ),
                          ),
                        );
                      }

                      // Stop pendiente: checkbox para marcar como entregada/no entregada
                      final isDelivered = _delivered[id] ?? true;
                      return Card(
                        margin: const EdgeInsets.only(bottom: 8),
                        child: CheckboxListTile(
                          value: isDelivered,
                          onChanged: (val) =>
                              _toggleDelivered(id, val ?? true),
                          title: Text(codigo),
                          subtitle: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(address, maxLines: 1, overflow: TextOverflow.ellipsis),
                              if (!isDelivered && _reasons[id] != null)
                                Text(
                                  'Motivo: ${_reasons[id]}',
                                  style: const TextStyle(
                                      color: Colors.red, fontSize: 12),
                                ),
                            ],
                          ),
                          secondary: Icon(
                            isDelivered
                                ? Icons.check_circle_outline
                                : Icons.remove_circle_outline,
                            color: isDelivered ? Colors.green : Colors.red,
                          ),
                        ),
                      );
                    },
                  ),
                ),
                if (allPending)
                  Padding(
                    padding: const EdgeInsets.fromLTRB(16, 0, 16, 24),
                    child: SizedBox(
                      width: double.infinity,
                      child: FilledButton.icon(
                        onPressed: _confirmGroup,
                        icon: const Icon(Icons.done_all),
                        label: const Text('Confirmar grupo'),
                      ),
                    ),
                  ),
              ],
            ),
    );
  }
}
