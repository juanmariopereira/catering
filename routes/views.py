from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.contrib.auth.mixins import LoginRequiredMixin
from django.views.generic import ListView, CreateView, UpdateView, DeleteView
from django.urls import reverse_lazy
from django.contrib import messages
from django.db.models import Q

from base.auth_utils import GROUP_ENTREGADOR
from .models import Entregador
from .forms import EntregadorForm

User = get_user_model()


def _get_entregador_group():
    group, _ = Group.objects.get_or_create(name=GROUP_ENTREGADOR)
    return group


class EntregadorListView(LoginRequiredMixin, ListView):
    model = Entregador
    template_name = 'routes/entregador_lista.html'
    context_object_name = 'entregadores'
    paginate_by = 30

    def get_queryset(self):
        queryset = super().get_queryset()
        busqueda = self.request.GET.get('q')
        if busqueda:
            queryset = queryset.filter(
                Q(nombre__icontains=busqueda) | Q(telefono__icontains=busqueda) | Q(vehiculo__icontains=busqueda)
            )
        activo = self.request.GET.get('activo')
        if activo is not None and activo != '':
            queryset = queryset.filter(activo=activo == '1')
        return queryset.order_by('nombre')


class EntregadorCreateView(LoginRequiredMixin, CreateView):
    model = Entregador
    form_class = EntregadorForm
    template_name = 'routes/entregador_form.html'
    success_url = reverse_lazy('routes:entregador_lista')

    def get_initial(self):
        initial = super().get_initial()
        initial['activo'] = True
        return initial

    def form_valid(self, form):
        username = form.cleaned_data['username'].strip()
        password = form.cleaned_data['password']
        entregador = form.save(commit=False)
        user = User.objects.create_user(
            username=username,
            password=password,
            first_name=entregador.nombre.split()[0] if entregador.nombre else '',
            last_name=' '.join(entregador.nombre.split()[1:]) if len(entregador.nombre.split()) > 1 else '',
        )
        _get_entregador_group().user_set.add(user)
        entregador.user = user
        entregador.save()
        messages.success(
            self.request,
            f'Entregador creado. Usuario de acceso: {username}. Guarda estos datos para entregárselos al entregador.',
        )
        return super().form_valid(form)


class EntregadorUpdateView(LoginRequiredMixin, UpdateView):
    model = Entregador
    form_class = EntregadorForm
    template_name = 'routes/entregador_form.html'
    success_url = reverse_lazy('routes:entregador_lista')

    def form_valid(self, form):
        entregador = form.save(commit=False)
        user = entregador.user
        password = form.cleaned_data.get('password')

        if not user and form.cleaned_data.get('username'):
            username = form.cleaned_data['username'].strip()
            if password:
                user = User.objects.create_user(
                    username=username,
                    password=password,
                    first_name=entregador.nombre.split()[0] if entregador.nombre else '',
                    last_name=' '.join(entregador.nombre.split()[1:]) if len(entregador.nombre.split()) > 1 else '',
                )
                _get_entregador_group().user_set.add(user)
                entregador.user = user
                messages.success(
                    self.request,
                    f'Entregador actualizado. Usuario de acceso creado: {username}. Guarda estos datos para el entregador.',
                )
            else:
                messages.warning(self.request, 'Para crear el usuario de acceso, indica una contraseña.')
        elif user and password:
            user.set_password(password)
            user.save()
            messages.success(self.request, 'Entregador y contraseña actualizados.')
        else:
            messages.success(self.request, 'Entregador actualizado.')
        # super().form_valid(form) llama a form.save() y redirige
        return super().form_valid(form)


class EntregadorDeleteView(LoginRequiredMixin, DeleteView):
    model = Entregador
    template_name = 'routes/entregador_confirm_delete.html'
    success_url = reverse_lazy('routes:entregador_lista')

    def form_valid(self, form):
        messages.success(self.request, 'Entregador eliminado exitosamente.')
        return super().form_valid(form)
