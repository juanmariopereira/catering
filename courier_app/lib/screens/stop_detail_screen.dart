import 'package:flutter/material.dart';
import 'package:provider/provider.dart';
import '../repositories/courier_repository.dart';

/// Stop detail: show address and actions. Buttons enabled/disabled strictly from backend.
class StopDetailScreen extends StatelessWidget {
  final int stopId;
  final Map<String, dynamic> stopData;

  const StopDetailScreen({super.key, required this.stopId, required this.stopData});

  @override
  Widget build(BuildContext context) {
    final state = stopData['state'] as String? ?? '';
    final address = stopData['address'] as String? ?? '';
    final codigo = stopData['codigo_entrega'] as String? ?? '';
    final canArrived = stopData['can_mark_arrived'] as bool? ?? false;
    final canDelivered = stopData['can_mark_delivered'] as bool? ?? false;
    final canFailed = stopData['can_mark_failed'] as bool? ?? false;
    final reasonBlocked = stopData['reason_if_blocked'] as String?;

    return Scaffold(
      appBar: AppBar(title: Text('Parada $codigo')),
      body: Padding(
        padding: const EdgeInsets.all(16.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Text('Estado: $state', style: Theme.of(context).textTheme.titleMedium),
            const SizedBox(height: 8),
            Text(address),
            if (reasonBlocked != null && reasonBlocked.isNotEmpty) ...[
              const SizedBox(height: 16),
              Text(
                reasonBlocked,
                style: TextStyle(color: Theme.of(context).colorScheme.error),
              ),
            ],
            const Spacer(),
            if (canArrived)
              FilledButton(
                onPressed: () => _sendAndRefresh(context, 'ATTEMPT_ARRIVE'),
                child: const Text('Marcar llegada'),
              ),
            if (canDelivered) ...[
              const SizedBox(height: 8),
              FilledButton(
                onPressed: () => _sendAndRefresh(context, 'ATTEMPT_DELIVER'),
                child: const Text('Marcar entregado'),
              ),
            ],
            if (canFailed) ...[
              const SizedBox(height: 8),
              OutlinedButton(
                onPressed: () => _sendFail(context),
                child: const Text('No entregado'),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Future<void> _sendAndRefresh(BuildContext context, String type) async {
    final repo = context.read<CourierRepository>();
    final ok = type == 'ATTEMPT_ARRIVE'
        ? await repo.attemptArrive(stopId)
        : await repo.attemptDeliver(stopId);
    if (context.mounted && ok) Navigator.of(context).pop();
  }

  Future<void> _sendFail(BuildContext context) async {
    final reason = await _askReason(context);
    if (reason == null) return; // cancelado
    if (!context.mounted) return;
    final ok = await context.read<CourierRepository>().attemptFail(stopId, reason: reason);
    if (context.mounted && ok) Navigator.of(context).pop();
  }

  Future<String?> _askReason(BuildContext context) {
    final controller = TextEditingController();
    return showDialog<String>(
      context: context,
      builder: (ctx) {
        String? errorText;
        return StatefulBuilder(
          builder: (ctx, setState) => AlertDialog(
            title: const Text('Motivo de no entrega'),
            content: TextField(
              controller: controller,
              autofocus: true,
              maxLines: 3,
              decoration: InputDecoration(
                hintText: 'Ej.: cliente ausente, dirección incorrecta…',
                errorText: errorText,
              ),
            ),
            actions: [
              TextButton(
                onPressed: () => Navigator.of(ctx).pop(),
                child: const Text('Cancelar'),
              ),
              FilledButton(
                onPressed: () {
                  final text = controller.text.trim();
                  if (text.isEmpty) {
                    setState(() => errorText = 'El motivo es obligatorio');
                    return;
                  }
                  Navigator.of(ctx).pop(text);
                },
                child: const Text('Confirmar'),
              ),
            ],
          ),
        );
      },
    );
  }
}
