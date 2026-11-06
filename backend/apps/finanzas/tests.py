"""Etapa 1 del PMV financiero: cargar lo que se baja del SII y clasificarlo."""

from datetime import date
from decimal import Decimal
from pathlib import Path
from unittest import mock

from django.contrib.auth import get_user_model
from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from rest_framework.test import APIClient

from apps.organizations.models import Organization
from apps.workspaces.models import ROLE_ADMIN, ROLE_EDITOR, ROLE_MEMBER

from . import constantes as c
from .importador import ArchivoNoReconocido, confirmar, importar, previsualizar
from .models import (Carga, Categoria, ConfiguracionTributaria, Contraparte, DocumentoTributario,
                     Proyecto)

User = get_user_model()
EJEMPLOS = Path(__file__).resolve().parents[2] / 'pruebas' / 'finanzas'


def ejemplo(nombre):
    return (EJEMPLOS / nombre).read_bytes()


def usuario(email):
    return User.objects.create_user(username=email, email=email, password='afable123')


class ImportadorTests(TestCase):
    def setUp(self):
        self.admin = usuario('admin@afable.test')
        self.org = Organization.objects.create(owner=self.admin, name='Empresa de Ejemplo')
        Categoria.asegurar_iniciales(self.org)

    def test_compras_detecta_el_libro_y_lee_los_montos(self):
        carga = importar(self.org, ejemplo('rcv_compras_ejemplo.csv'), 'compras.csv')
        self.assertEqual(carga.libro, c.LIBRO_COMPRAS)
        self.assertGreater(carga.nuevos, 20)
        d = DocumentoTributario.objects.filter(organization=self.org, tipo_documento='33').first()
        self.assertEqual(d.monto_total, d.monto_neto + d.monto_iva + d.monto_exento)
        self.assertRegex(d.rut, r'^\d{7,8}-[\dK]$')

    def test_la_fila_con_rut_malo_queda_en_errores_con_su_folio(self):
        carga = importar(self.org, ejemplo('rcv_compras_ejemplo.csv'), 'compras.csv')
        self.assertEqual(len(carga.errores), 1)
        self.assertIn('RUT', carga.errores[0]['motivo'])
        self.assertTrue(carga.errores[0]['folio'])

    def test_recargar_el_mismo_archivo_no_duplica(self):
        primera = importar(self.org, ejemplo('rcv_ventas_ejemplo.csv'), 'ventas.csv')
        segunda = importar(self.org, ejemplo('rcv_ventas_ejemplo.csv'), 'ventas.csv')
        self.assertEqual(segunda.nuevos, 0)
        self.assertEqual(segunda.duplicados, primera.nuevos)
        self.assertEqual(DocumentoTributario.objects.filter(libro=c.LIBRO_VENTAS).count(), primera.nuevos)

    def test_la_nota_de_credito_resta(self):
        importar(self.org, ejemplo('rcv_ventas_ejemplo.csv'), 'ventas.csv')
        nc = DocumentoTributario.objects.get(organization=self.org, tipo_documento='61')
        self.assertEqual(nc.signo, -1)

    def test_honorarios_guarda_lo_retenido_y_salta_las_anuladas(self):
        carga = importar(self.org, ejemplo('honorarios_recibidos_ejemplo.csv'), 'bhe.csv')
        self.assertEqual(carga.libro, c.LIBRO_HONORARIOS)
        self.assertEqual(carga.nuevos, 6)                      # 7 filas, 1 anulada
        b = DocumentoTributario.objects.filter(libro=c.LIBRO_HONORARIOS).first()
        self.assertEqual(b.tipo_documento, 'BHE')
        self.assertGreater(b.monto_retenido, 0)

    def test_un_archivo_que_no_es_del_sii_se_rechaza_explicado(self):
        with self.assertRaises(ArchivoNoReconocido):
            importar(self.org, b'nombre,edad\nAna,30\n', 'otra.csv')

    def test_la_regla_del_proveedor_clasifica_al_cargar(self):
        arriendo = Categoria.objects.get(organization=self.org, nombre='Arriendo')
        Contraparte.objects.create(organization=self.org, libro=c.LIBRO_COMPRAS, rut='77222333-4',
                                   regla_activa=True, categoria=arriendo)
        importar(self.org, ejemplo('rcv_compras_ejemplo.csv'), 'compras.csv')
        docs = DocumentoTributario.objects.filter(rut='77222333-4')
        self.assertTrue(docs.exists())
        for d in docs:
            self.assertEqual(d.categoria, arriendo)
            self.assertEqual(d.estado, DocumentoTributario.CONFIRMADO)
            self.assertEqual(d.origen_clasificacion, DocumentoTributario.ORIGEN_REGLA)

    def test_previsualizar_no_crea_documentos(self):
        carga = previsualizar(self.org, ejemplo('rcv_compras_ejemplo.csv'), 'compras.csv')
        self.assertEqual(carga.estado, Carga.BORRADOR)
        self.assertGreater(len(carga.filas_previas), 20)
        self.assertFalse(DocumentoTributario.objects.exists())
        self.assertTrue(all(f['contraparte_nueva'] for f in carga.filas_previas))

    def test_confirmar_aplica_lo_decidido_y_crea_las_fichas(self):
        carga = previsualizar(self.org, ejemplo('rcv_compras_ejemplo.csv'), 'compras.csv')
        mercaderia = Categoria.objects.get(organization=self.org, nombre='Costo de mercadería')
        primera = carga.filas_previas[0]
        confirmar(carga, {primera['n']: {'categoria': mercaderia.id, 'pagado': False}})
        d = DocumentoTributario.objects.get(organization=self.org, folio=primera['folio'],
                                            rut=primera['rut'])
        self.assertEqual(d.categoria, mercaderia)
        self.assertEqual(d.estado, DocumentoTributario.CONFIRMADO)
        self.assertFalse(d.pagado)
        self.assertIsNotNone(d.contraparte)
        self.assertEqual(Contraparte.objects.filter(organization=self.org).count(),
                         len({f['rut'] for f in carga.ya_estaban} | set(
                             DocumentoTributario.objects.values_list('rut', flat=True))))

    def test_lo_ya_cargado_aparece_en_ya_estaban(self):
        importar(self.org, ejemplo('rcv_ventas_ejemplo.csv'), 'ventas.csv')
        carga = previsualizar(self.org, ejemplo('rcv_ventas_ejemplo.csv'), 'ventas.csv')
        self.assertEqual(carga.filas_previas, [])
        self.assertGreater(len(carga.ya_estaban), 20)

    def test_propone_la_categoria_del_ultimo_documento_del_mismo_rut(self):
        carga = previsualizar(self.org, ejemplo('rcv_compras_ejemplo.csv'), 'compras.csv')
        software = Categoria.objects.get(organization=self.org, nombre='Software y suscripciones')
        cloud = [f for f in carga.filas_previas if f['rut'] == '76333444-5']
        confirmar(carga, {cloud[0]['n']: {'categoria': software.id}})
        # Un archivo nuevo del mismo proveedor: propone lo de la última vez.
        DocumentoTributario.objects.filter(rut='76333444-5').exclude(folio=cloud[0]['folio']).delete()
        otra = previsualizar(self.org, ejemplo('rcv_compras_ejemplo.csv'), 'compras.csv')
        propuestas = {f['categoria'] for f in otra.filas_previas if f['rut'] == '76333444-5'}
        self.assertEqual(propuestas, {software.id})
        self.assertTrue(all(f['origen'] == 'historial' for f in otra.filas_previas if f['rut'] == '76333444-5'))

    def test_se_da_por_pagado_lo_vencido_segun_el_plazo(self):
        carga = previsualizar(self.org, ejemplo('rcv_compras_ejemplo.csv'), 'compras.csv')
        from datetime import date
        for f in carga.filas_previas:
            self.assertEqual(f['pagado'], date.fromisoformat(f['fecha_vencimiento']) < date.today())

    def test_retencion_por_anio(self):
        self.assertEqual(c.retencion_honorarios(2026), Decimal('15.25'))
        self.assertEqual(c.retencion_honorarios(2031), Decimal('17.00'))   # el año más cercano


class FinanzasAPITests(TestCase):
    def setUp(self):
        self.client = APIClient()
        self.admin = usuario('admin@afable.test')
        self.editor = usuario('editor@afable.test')
        self.miembro = usuario('miembro@afable.test')
        self.ajeno = usuario('ajeno@afable.test')
        self.org = Organization.objects.create(owner=self.admin, name='Empresa de Ejemplo')
        self.org.agregar_miembro(self.admin, ROLE_ADMIN)
        self.org.agregar_miembro(self.editor, ROLE_EDITOR)
        self.org.agregar_miembro(self.miembro, ROLE_MEMBER)
        otra = Organization.objects.create(owner=self.ajeno, name='Otra Empresa')
        otra.agregar_miembro(self.ajeno, ROLE_ADMIN)
        self.base = f'/api/v1/workspaces/{self.org.slug}/finanzas'

    def _previsualizar(self, nombre, como=None):
        self.client.force_authenticate(como or self.editor)
        archivo = SimpleUploadedFile(nombre, ejemplo(nombre), content_type='text/csv')
        return self.client.post(f'{self.base}/cargas/', {'file': archivo}, format='multipart')

    def _subir(self, nombre, como=None):
        """Revisar y confirmar sin cambios: lo que hace quien acepta lo propuesto."""
        r = self._previsualizar(nombre, como)
        if r.status_code != 201:
            return r
        return self.client.post(f'{self.base}/cargas/{r.data["id"]}/confirmar/', {}, format='json')

    def test_el_editor_carga_y_el_miembro_ve(self):
        r = self._subir('rcv_compras_ejemplo.csv')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['estado'], 'importada')
        self.assertGreater(r.data['nuevos'], 0)
        self.client.force_authenticate(self.miembro)
        r = self.client.get(f'{self.base}/documentos/?libro=compras')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r.data['total'], r.data['por_revisar'])

    def test_el_miembro_no_carga(self):
        r = self._previsualizar('rcv_compras_ejemplo.csv', como=self.miembro)
        self.assertEqual(r.status_code, 403)

    def test_la_revision_trae_el_resumen_y_cancelar_no_deja_nada(self):
        r = self._previsualizar('rcv_compras_ejemplo.csv')
        self.assertEqual(r.data['estado'], 'borrador')
        resumen = r.data['resumen']
        self.assertEqual(resumen['total'], sum(f['signo'] * f['monto_total'] for f in r.data['filas_previas']))
        self.assertEqual(resumen['sin_categoria'], len(r.data['filas_previas']))
        self.assertGreater(len(resumen['contrapartes_nuevas']), 0)
        self.assertEqual(self.client.delete(f'{self.base}/cargas/{r.data["id"]}/').status_code, 204)
        self.assertFalse(DocumentoTributario.objects.exists())
        self.assertFalse(Carga.objects.exists())

    def test_confirmar_dos_veces_no_duplica(self):
        r = self._previsualizar('rcv_ventas_ejemplo.csv')
        url = f'{self.base}/cargas/{r.data["id"]}/confirmar/'
        self.assertEqual(self.client.post(url, {}, format='json').status_code, 200)
        self.assertEqual(self.client.post(url, {}, format='json').status_code, 404)

    def test_la_ia_sugiere_en_la_revision(self):
        r = self._previsualizar('rcv_compras_ejemplo.csv')
        with mock.patch('apps.finanzas.clasificador._preguntar',
                        return_value='{"77222333-4": "Arriendo"}'):
            s = self.client.post(f'{self.base}/cargas/{r.data["id"]}/sugerir/')
        self.assertGreater(s.data['sugeridos'], 0)
        filas = [f for f in s.data['filas_previas'] if f['rut'] == '77222333-4']
        self.assertTrue(all(f['origen'] == 'ia' for f in filas))

    def test_marcar_pagado_registra_la_fecha(self):
        self._subir('rcv_ventas_ejemplo.csv')
        d = DocumentoTributario.objects.filter(organization=self.org).first()
        r = self.client.patch(f'{self.base}/documentos/{d.id}/', {'pagado': True}, format='json')
        self.assertTrue(r.data['pagado'])
        self.assertIsNotNone(r.data['fecha_pago'])

    def test_fichas_de_proveedores_con_su_plazo(self):
        self._subir('rcv_compras_ejemplo.csv')
        r = self.client.get(f'{self.base}/contrapartes/?libro=compras')
        self.assertEqual(r.status_code, 200)
        ficha = next(x for x in r.data if x['rut'] == '76111222-3')
        self.assertGreater(ficha['documentos'], 0)
        self.assertEqual(ficha['plazo'], c.PLAZO_PAGO_POR_DEFECTO)
        r = self.client.patch(f'{self.base}/contrapartes/{ficha["id"]}/', {'plazo_dias': 12}, format='json')
        self.assertEqual(r.data['plazo'], 12)

    def test_otra_empresa_no_existe(self):
        self.client.force_authenticate(self.ajeno)
        self.assertEqual(self.client.get(f'{self.base}/documentos/').status_code, 404)

    def test_la_categoria_se_asocia_a_su_cuenta_contable(self):
        self.client.force_authenticate(self.miembro)
        cat = self.client.get(f'{self.base}/categorias/').data[0]
        self.assertEqual(cat['cuenta_codigo'], '')
        url = f'{self.base}/categorias/{cat["id"]}/'
        self.assertEqual(self.client.patch(url, {'cuenta_codigo': '4101'}, format='json').status_code, 403)
        self.client.force_authenticate(self.editor)
        r = self.client.patch(url, {'cuenta_codigo': ' 4101 ', 'cuenta_nombre': 'Ingresos por ventas'}, format='json')
        self.assertEqual((r.data['cuenta_codigo'], r.data['cuenta_nombre']), ('4101', 'Ingresos por ventas'))
        self.client.force_authenticate(self.ajeno)
        self.assertEqual(self.client.patch(url, {'cuenta_codigo': 'x'}, format='json').status_code, 404)

    def test_configuracion_parte_con_la_sugerida_sin_confirmar(self):
        self.client.force_authenticate(self.miembro)
        r = self.client.get(f'{self.base}/configuracion/')
        self.assertEqual(r.data['regimen'], c.REGIMEN_PRO_PYME_GENERAL)
        self.assertFalse(r.data['tasa_ppm_confirmada'])

    def test_cambiar_regimen_propone_la_tasa_y_fijarla_la_confirma(self):
        self.client.force_authenticate(self.editor)
        r = self.client.put(f'{self.base}/configuracion/', {'regimen': c.REGIMEN_GENERAL}, format='json')
        self.assertEqual(Decimal(r.data['tasa_ppm']), c.PPM_SUGERIDA[c.REGIMEN_GENERAL])
        self.assertFalse(r.data['tasa_ppm_confirmada'])
        r = self.client.put(f'{self.base}/configuracion/', {'tasa_ppm': '1,7'}, format='json')
        self.assertEqual(Decimal(r.data['tasa_ppm']), Decimal('1.7'))
        self.assertTrue(r.data['tasa_ppm_confirmada'])

    def test_clasificar_con_regla_la_aplica_hacia_atras(self):
        self._subir('rcv_compras_ejemplo.csv')
        docs = DocumentoTributario.objects.filter(organization=self.org, rut='76333444-5')
        self.assertGreater(docs.count(), 1)
        software = Categoria.objects.get(organization=self.org, nombre='Software y suscripciones')
        r = self.client.patch(f'{self.base}/documentos/{docs.first().id}/',
                              {'categoria': software.id, 'estado': 'confirmado', 'crear_regla': True},
                              format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['regla_aplicada_a'], docs.count() - 1)
        self.assertFalse(docs.exclude(categoria=software).exists())

    def test_el_reparto_no_puede_pasar_de_100(self):
        self._subir('rcv_compras_ejemplo.csv')
        a = Proyecto.objects.create(organization=self.org, nombre='Obra Las Condes')
        b = Proyecto.objects.create(organization=self.org, nombre='Local Ñuñoa')
        d = DocumentoTributario.objects.filter(organization=self.org).first()
        url = f'{self.base}/documentos/{d.id}/'
        r = self.client.patch(url, {'asignaciones': [{'proyecto': a.id, 'porcentaje': 70},
                                                     {'proyecto': b.id, 'porcentaje': 40}]}, format='json')
        self.assertEqual(r.status_code, 400)
        r = self.client.patch(url, {'asignaciones': [{'proyecto': a.id, 'porcentaje': 60},
                                                     {'proyecto': b.id, 'porcentaje': 40}]}, format='json')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(len(r.data['asignaciones']), 2)

    def test_lote_clasifica_y_confirma(self):
        self._subir('rcv_ventas_ejemplo.csv')
        ids = list(DocumentoTributario.objects.filter(organization=self.org).values_list('id', flat=True)[:5])
        servicios = Categoria.objects.get(organization=self.org, nombre='Venta de servicios')
        r = self.client.post(f'{self.base}/documentos/lote/',
                             {'ids': ids, 'categoria': servicios.id, 'confirmar': True}, format='json')
        self.assertEqual(r.data['actualizados'], 5)
        self.assertEqual(DocumentoTributario.objects.filter(id__in=ids, estado='confirmado').count(), 5)

    def test_la_ia_sugiere_sin_confirmar_y_respeta_el_tipo(self):
        self._subir('rcv_compras_ejemplo.csv')
        # La IA propone "Arriendo" para el arrendador y, por error, un ingreso para la eléctrica.
        respuesta = ('{"compras|77222333-4": "Arriendo", '
                     '"compras|96555666-7": "Venta de servicios"}')
        with mock.patch('apps.finanzas.clasificador._preguntar', return_value=respuesta):
            r = self.client.post(f'{self.base}/documentos/sugerir/')
        self.assertGreater(r.data['sugeridos'], 0)
        arriendo = DocumentoTributario.objects.filter(rut='77222333-4').first()
        self.assertEqual(arriendo.categoria.nombre, 'Arriendo')
        self.assertEqual(arriendo.estado, DocumentoTributario.POR_REVISAR)   # la persona confirma
        self.assertEqual(arriendo.origen_clasificacion, 'ia')
        electrica = DocumentoTributario.objects.filter(rut='96555666-7').first()
        self.assertIsNone(electrica.categoria)                              # ingreso a una compra: no


class NumerosTests(TestCase):
    """Etapa 2: los números se calculan bien desde los documentos."""

    def setUp(self):
        self.client = APIClient()
        self.admin = usuario('admin@afable.test')
        self.org = Organization.objects.create(owner=self.admin, name='Empresa de Ejemplo')
        self.org.agregar_miembro(self.admin, ROLE_ADMIN)
        self.client.force_authenticate(self.admin)
        self.base = f'/api/v1/workspaces/{self.org.slug}/finanzas'
        Categoria.asegurar_iniciales(self.org)
        for f in ('rcv_compras_ejemplo.csv', 'rcv_ventas_ejemplo.csv', 'honorarios_recibidos_ejemplo.csv'):
            importar(self.org, ejemplo(f), f)

    def _esperado(self, mes):
        ventas = DocumentoTributario.objects.filter(organization=self.org, libro='ventas', fecha__month=mes)
        compras = DocumentoTributario.objects.filter(organization=self.org, libro='compras', fecha__month=mes)
        bhe = DocumentoTributario.objects.filter(organization=self.org, libro='honorarios', fecha__month=mes)
        ingresos = sum(d.signo * (d.monto_neto + d.monto_exento) for d in ventas)
        gastos = sum(d.signo * (d.monto_neto + d.monto_exento) for d in compras) + sum(d.monto_total for d in bhe)
        debito = sum(d.signo * d.monto_iva for d in ventas)
        credito = sum(d.signo * d.monto_iva for d in compras)
        return ingresos, gastos, debito, credito, sum(d.monto_retenido for d in bhe)

    def test_resumen_cuadra_con_los_documentos(self):
        r = self.client.get(f'{self.base}/resumen/?anio=2026').data
        octubre = r['meses'][9]
        ingresos, gastos, *_ = self._esperado(10)
        self.assertEqual(octubre['ingresos'], ingresos)
        self.assertEqual(octubre['gastos'], gastos)
        self.assertEqual(octubre['ganancia'], ingresos - gastos)
        self.assertIn(2026, r['anios'])

    def test_f29_estimado(self):
        r = self.client.get(f'{self.base}/impuestos/?anio=2026').data
        oct_ = next(x for x in r['meses'] if x['mes'] == 10)
        ingresos, _, debito, credito, retencion = self._esperado(10)
        tasa = ConfiguracionTributaria.de(self.org).tasa_ppm
        ppm = int((Decimal(ingresos) * tasa / 100).quantize(Decimal('1')))
        self.assertEqual(oct_['iva_neto'], debito - credito)
        self.assertEqual(oct_['ppm'], ppm)
        self.assertEqual(oct_['retencion'], retencion)
        self.assertEqual(oct_['estimado'], max(debito - credito, 0) + ppm + retencion)
        self.assertEqual(oct_['vence'], '2026-11-20')

    def test_marcar_f29_pagado(self):
        r = self.client.patch(f'{self.base}/impuestos/2026/9/', {'pagado': True, 'monto_pagado': 1000}, format='json')
        sep = next(x for x in r.data['meses'] if x['mes'] == 9)
        self.assertTrue(sep['pagado'])
        self.assertEqual(sep['monto_pagado'], 1000)

    def test_por_categoria_suma_100(self):
        servicios = Categoria.objects.get(organization=self.org, nombre='Venta de servicios')
        DocumentoTributario.objects.filter(organization=self.org, libro='ventas').update(categoria=servicios)
        r = self.client.get(f'{self.base}/por-categoria/?periodo=anio&anio=2026').data
        self.assertEqual(r['ingresos']['filas'][0]['categoria'], 'Venta de servicios')
        self.assertEqual(r['gastos']['filas'][-1]['acumulado'], 100)

    def test_margen_por_proyecto_respeta_el_reparto(self):
        a = Proyecto.objects.create(organization=self.org, nombre='Obra A')
        venta = DocumentoTributario.objects.filter(organization=self.org, libro='ventas', tipo_documento='33').first()
        compra = DocumentoTributario.objects.filter(organization=self.org, libro='compras', tipo_documento='33').first()
        from .models import Asignacion
        Asignacion.objects.create(documento=venta, proyecto=a, porcentaje=100)
        Asignacion.objects.create(documento=compra, proyecto=a, porcentaje=50)
        r = self.client.get(f'{self.base}/proyectos/margen/').data
        p = r['proyectos'][0]
        self.assertEqual(p['ingresos'], venta.monto_neto + venta.monto_exento)
        self.assertEqual(p['gastos'], int((compra.monto_neto + compra.monto_exento) / 2))


class _ConCartolas(TestCase):
    """Empresa con los archivos del SII de ejemplo y dos cuentas (Santander y BCI)."""

    def setUp(self):
        from .models import CuentaBancaria
        self.client = APIClient()
        self.admin = usuario('admin@afable.test')
        self.org = Organization.objects.create(owner=self.admin, name='Empresa de Ejemplo')
        self.org.agregar_miembro(self.admin, ROLE_ADMIN)
        self.client.force_authenticate(self.admin)
        self.base = f'/api/v1/workspaces/{self.org.slug}/finanzas'
        for f in ('rcv_compras_ejemplo.csv', 'rcv_ventas_ejemplo.csv', 'honorarios_recibidos_ejemplo.csv'):
            importar(self.org, ejemplo(f), f)
        self.sant = CuentaBancaria.objects.create(organization=self.org, banco='Santander')
        self.bci = CuentaBancaria.objects.create(organization=self.org, banco='BCI')

    def _cargar(self):
        from . import conciliacion
        conciliacion.cargar_cartola(self.sant, ejemplo('cartola_santander_ejemplo.csv'), 'santander.csv')
        conciliacion.cargar_cartola(self.bci, ejemplo('cartola_bci_ejemplo.csv'), 'bci.csv')

    def _mov(self, texto):
        from .models import MovimientoBancario
        return MovimientoBancario.objects.get(organization=self.org, descripcion__icontains=texto)



class ConciliacionTests(_ConCartolas):
    """El cuadre: cartolas de prueba generadas desde los mismos archivos del SII."""

    def test_recargar_la_cartola_no_duplica(self):
        from . import conciliacion
        self._cargar()
        otra = conciliacion.cargar_cartola(self.sant, ejemplo('cartola_santander_ejemplo.csv'), 'santander.csv')
        self.assertEqual(otra.nuevos, 0)
        self.assertGreater(otra.duplicados, 15)

    def test_cruza_lo_claro_y_deja_pagado_con_la_fecha_del_banco(self):
        self._cargar()
        from .models import MovimientoBancario
        conciliados = MovimientoBancario.objects.filter(organization=self.org, estado='conciliado')
        self.assertGreater(conciliados.count(), 10)
        for mov in conciliados:
            for d in mov.documentos.all():
                self.assertTrue(d.pagado)
                self.assertEqual(d.fecha_pago, mov.fecha)

    def test_un_pago_de_dos_facturas_del_mismo_cliente(self):
        self._cargar()
        from .models import MovimientoBancario
        dobles = [m for m in MovimientoBancario.objects.filter(organization=self.org, estado='conciliado')
                  if m.documentos.count() == 2]
        self.assertEqual(len(dobles), 1)
        self.assertEqual(sum(d.monto_total for d in dobles[0].documentos.all()), dobles[0].monto)

    def test_una_suma_de_facturas_es_del_proveedor_que_nombra_la_glosa(self):
        """⚠️ Regresión real (25-10-2026): el pago a Ferretería quedó con dos facturas de
        Transportes porque las de Transportes también sumaban el monto."""
        from . import conciliacion
        from .models import MovimientoBancario
        self._cargar()
        conciliacion.cargar_cartola(self.sant, ejemplo('cartola_santander_octubre_pendientes.csv'), 'oct.csv')
        mov = MovimientoBancario.objects.get(organization=self.org, monto=-243950)
        self.assertTrue(all('Ferretería' in d.razon_social for d in mov.documentos.all()))

    def test_honorarios_se_cruzan_por_el_liquido(self):
        self._cargar()
        bhe = DocumentoTributario.objects.filter(organization=self.org, libro='honorarios', pagado=True,
                                                 movimientos__isnull=False)
        self.assertGreaterEqual(bhe.count(), 3)

    def test_glosas_comision_e_impuestos_se_identifican_solas(self):
        self._cargar()
        self.assertEqual(self._mov('COMISION').tipo_sin_documento, 'comision')
        self.assertEqual(self._mov('PAGO F29').tipo_sin_documento, 'impuestos')

    def test_traspaso_se_sugiere_y_se_confirma(self):
        self._cargar()
        sale, entra = self._mov('TRASPASO A CUENTA'), self._mov('TRASPASO DESDE')
        self.assertEqual(sale.pareja_id, entra.id)
        self.assertEqual(sale.estado, 'pendiente')
        r = self.client.post(f'{self.base}/movimientos/{sale.id}/traspaso/')
        self.assertEqual(r.data['estado'], 'traspaso')
        entra.refresh_from_db()
        self.assertEqual(entra.estado, 'traspaso')

    def test_identificar_y_deshacer(self):
        self._cargar()
        retiro = self._mov('ALEXIS GONZALEZ')
        r = self.client.post(f'{self.base}/movimientos/{retiro.id}/identificar/', {'tipo': 'retiro_dueno'}, format='json')
        self.assertEqual(r.data['estado'], 'identificado')
        from .models import MovimientoBancario
        pago = next(m for m in MovimientoBancario.objects.filter(organization=self.org, estado='conciliado')
                    if m.documentos.count() == 1)
        doc = pago.documentos.first()
        self.client.post(f'{self.base}/movimientos/{pago.id}/deshacer/')
        doc.refresh_from_db()
        self.assertFalse(doc.pagado)

    def test_el_cuadre_y_cerrar_el_mes(self):
        self._cargar()
        r = self.client.get(f'{self.base}/cuadre/?anio=2026&mes=9').data
        self.assertEqual(r['cuadraron_solos'] + r['los_cuadro_usted'] + r['pendientes'], r['movimientos'])
        self.assertEqual(r['posibles_traspasos']['pares'], 1)
        self.assertGreater(r['porcentaje'], 70)
        r = self.client.post(f'{self.base}/cuadre/cierres/', {'anio': 2026, 'mes': 9}, format='json')
        self.assertTrue(r.data['cerrado'])
        retiro = self._mov('ALEXIS GONZALEZ')
        r = self.client.post(f'{self.base}/movimientos/{retiro.id}/identificar/', {'tipo': 'retiro_dueno'}, format='json')
        self.assertEqual(r.status_code, 400)                    # mes cerrado: no se toca


class TesoreriaTests(_ConCartolas):
    """Etapa 3: con las mismas cartolas de prueba, la plata cuadra."""

    def test_por_cobrar_suma_lo_no_pagado(self):
        self._cargar()
        r = self.client.get(f'{self.base}/cuentas-por/cobrar/').data
        from .conciliacion import monto_a_pagar
        esperado = sum(monto_a_pagar(d) for d in DocumentoTributario.objects.filter(
            organization=self.org, libro='ventas', pagado=False))
        self.assertEqual(r['total'], esperado)
        self.assertEqual(sum(r['tramos'].values()), r['total'])
        self.assertEqual(sum(x['monto'] for x in r['por_contraparte']), r['total'])

    def test_por_pagar_honorarios_por_el_liquido(self):
        r = self.client.get(f'{self.base}/cuentas-por/pagar/').data
        bhe = [f for f in r['documentos'] if f['tipo_nombre'].startswith('Boleta de honorarios')]
        for f in bhe:
            d = DocumentoTributario.objects.get(id=f['id'])
            self.assertEqual(f['monto'], d.monto_total - d.monto_retenido)

    def test_caja_sin_cartolas_no_inventa(self):
        r = self.client.get(f'{self.base}/caja/').data
        self.assertIsNone(r['disponible'])
        self.assertIsNone(r['puede_retirar'])

    def test_caja_con_cartolas(self):
        self._cargar()
        r = self.client.get(f'{self.base}/caja/').data
        self.assertEqual(r['disponible'], sum(x['saldo'] for x in r['cuentas'] if x['saldo'] is not None))
        self.assertEqual(r['puede_retirar'], max(0, r['disponible'] - r['salidas_comprometidas'] - r['gasto_mensual']))
        self.assertEqual(r['saldo_30_dias'], r['disponible'] + r['entradas_esperadas'] - r['salidas_comprometidas'])
        self.assertEqual(r['fuente_gasto'], 'banco')

    def test_cuenta_del_dueno(self):
        self._cargar()
        retiro = self._mov('ALEXIS GONZALEZ')
        self.client.post(f'{self.base}/movimientos/{retiro.id}/identificar/', {'tipo': 'retiro_dueno'}, format='json')
        r = self.client.get(f'{self.base}/cuenta-dueno/').data
        self.assertEqual(r['retiros'], 1200000)
        self.assertTrue(any(m['tipo'] == 'impuestos' for m in r['movimientos']))


class HerramientaChatTests(_ConCartolas):
    """Etapa 4: la herramienta que usa el chat devuelve los mismos números que las pantallas."""

    def test_se_ofrece_solo_con_datos(self):
        from services.agent_tools import _tools_spec
        nombres = [t['name'] for t in _tools_spec(self.org)]
        self.assertIn('consultar_finanzas', nombres)
        vacia = Organization.objects.create(owner=self.admin, name='Sin datos')
        self.assertNotIn('consultar_finanzas', [t['name'] for t in _tools_spec(vacia)])

    def test_responde_lo_mismo_que_las_pantallas(self):
        from . import calculos, tesoreria
        from .herramienta import ejecutar
        self._cargar()
        f29 = ejecutar(self.org, {'consulta': 'f29', 'anio': 2026})
        self.assertEqual(f29['meses'], calculos.f29(self.org, 2026)['meses'])
        caja = ejecutar(self.org, {'consulta': 'caja'})
        self.assertEqual(caja['puede_retirar'], tesoreria.caja(self.org)['puede_retirar'])
        self.assertIn('error', ejecutar(self.org, {'consulta': 'otra'}))



class AutomatizacionesTests(_ConCartolas):
    """Las automatizaciones avisan solo cuando hay algo que decir, y no repiten."""

    def _auto(self, clave):
        from .models import AutomatizacionModulo
        return AutomatizacionModulo.objects.create(organization=self.org, clave=clave, activa=True, por_correo=True)

    def test_catalogo_por_modulo(self):
        r = self.client.get(f'{self.base}/automatizaciones/?modulo=finanzas').data
        self.assertTrue(r)
        self.assertTrue(all(a['modulo'] == 'finanzas' and not a['activa'] for a in r))

    def test_activar_y_probar_ahora_no_avisa(self):
        from apps.notificaciones.models import Notificacion
        r = self.client.patch(f'{self.base}/automatizaciones/f29_aviso/', {'activa': True}, format='json')
        self.assertTrue(r.data['activa'])
        r = self.client.post(f'{self.base}/automatizaciones/f29_aviso/')
        self.assertTrue(r.data['aviso'])
        self.assertIn('F29', r.data['titulo'])
        self.assertFalse(Notificacion.objects.exists())          # probar no le avisa a nadie

    def test_avisa_una_vez_por_marca(self):
        from django.core import mail
        from unittest import mock
        from apps.notificaciones.models import Notificacion
        from . import automatizaciones as a
        auto = self._auto('f29_aviso')
        hoy = date(2026, 11, 17)                                   # el F29 de octubre vence el 20-11
        with mock.patch.object(a, '_hoy', return_value=hoy):
            primera = a.ejecutar(auto)
            segunda = a.ejecutar(auto)
        self.assertTrue(primera['aviso'])
        self.assertFalse(segunda['aviso'])
        self.assertEqual(Notificacion.objects.filter(user=self.admin).count(), 1)
        self.assertEqual(len(mail.outbox), 1)

    def test_caja_corta_avisa_solo_si_falta(self):
        from unittest import mock
        from . import automatizaciones as a
        self._cargar()
        auto = self._auto('caja_corta')
        r = a.ejecutar(auto)                                      # con los datos de ejemplo la caja alcanza
        self.assertFalse(r['aviso'])
        with mock.patch('apps.finanzas.tesoreria.caja', return_value={
                'disponible': 100, 'saldo_30_dias': -500, 'entradas_esperadas': 0, 'salidas_comprometidas': 600}):
            self.assertTrue(a.ejecutar(auto)['aviso'])
            self.assertFalse(a.ejecutar(auto)['aviso'])          # mismo estado: no repite

    def test_correr_pendientes_sigue_la_programacion(self):
        from datetime import datetime
        from django.utils import timezone
        from . import automatizaciones as a
        auto = self._auto('cobros_vencidos')                     # del catálogo: cada lunes a las 8
        domingo = timezone.make_aware(datetime(2026, 10, 18, 20, 0))
        self.assertEqual(a.correr_pendientes(domingo), 0)        # recién activada: solo se agenda
        auto.refresh_from_db()
        self.assertEqual(timezone.localtime(auto.proxima_ejecucion), timezone.make_aware(datetime(2026, 10, 19, 8, 0)))
        temprano = timezone.make_aware(datetime(2026, 10, 19, 7, 0))
        self.assertEqual(a.correr_pendientes(temprano), 0)
        tarde = timezone.make_aware(datetime(2026, 10, 19, 9, 0))
        self.assertEqual(a.correr_pendientes(tarde), 1)
        self.assertEqual(a.correr_pendientes(tarde), 0)          # la siguiente es el otro lunes
        auto.refresh_from_db()
        self.assertEqual(timezone.localtime(auto.proxima_ejecucion).date(), date(2026, 10, 26))

    def test_siguiente_ejecucion_por_frecuencia(self):
        from datetime import datetime
        from django.utils import timezone
        from . import automatizaciones as a
        jueves = timezone.make_aware(datetime(2026, 10, 22, 10, 0))
        diaria = a.siguiente(a._prog('diaria', hora=9), jueves)
        self.assertEqual(timezone.localtime(diaria), timezone.make_aware(datetime(2026, 10, 23, 9, 0)))
        viernes = a.siguiente(a._prog('semanal', hora=18, dia_semana=4), jueves)
        self.assertEqual(timezone.localtime(viernes), timezone.make_aware(datetime(2026, 10, 23, 18, 0)))
        mensual = a.siguiente(a._prog('mensual', hora=8, dia_mes=3), jueves)
        self.assertEqual(timezone.localtime(mensual), timezone.make_aware(datetime(2026, 11, 3, 8, 0)))

    def test_programar_y_elegir_seguidores(self):
        url = f'{self.base}/automatizaciones/cobros_vencidos/'
        r = self.client.patch(url, {'activa': True, 'frecuencia': 'mensual', 'dia_mes': 5, 'hora': 10}, format='json')
        self.assertEqual(r.status_code, 200, r.content)
        self.assertEqual(r.data['cuando'], 'El día 5 de cada mes a las 10:00')
        self.assertIsNotNone(r.data['proxima_ejecucion'])
        self.assertEqual(self.client.patch(url, {'dia_mes': 31}, format='json').status_code, 400)
        r = self.client.patch(url, {'seguidores': [self.admin.id]}, format='json')
        self.assertEqual(r.data['seguidores'], [self.admin.id])
        ajeno = usuario('fuera@afable.test')
        self.assertEqual(self.client.patch(url, {'seguidores': [ajeno.id]}, format='json').status_code, 400)

    def test_avisa_solo_a_los_seguidores_y_por_whatsapp(self):
        from unittest import mock
        from django.core import mail
        from django.test import override_settings
        from apps.notificaciones.models import Notificacion
        from . import automatizaciones as a
        self.admin.telefono = '56911112222'
        self.admin.save()
        auto = self._auto('f29_aviso')
        auto.por_whatsapp = True
        auto.save()
        auto.seguidores.set([self.admin])
        with override_settings(WHATSAPP_TOKEN='t', WHATSAPP_PHONE_NUMBER_ID='1'), \
                mock.patch('apps.notificaciones.whatsapp.requests.post') as post, \
                mock.patch.object(a, '_hoy', return_value=date(2026, 11, 17)):
            post.return_value.status_code = 200
            self.assertTrue(a.ejecutar(auto)['aviso'])
        self.assertEqual(set(Notificacion.objects.values_list('user_id', flat=True)), {self.admin.id})
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(post.call_args.kwargs['json']['to'], '56911112222')
        self.assertEqual(post.call_args.kwargs['json']['type'], 'template')

    def test_whatsapp_sin_configurar_no_envia(self):
        from unittest import mock
        from apps.notificaciones import whatsapp
        with mock.patch('apps.notificaciones.whatsapp.requests.post') as post:
            self.assertFalse(whatsapp.enviar('56911112222', 'x', 'y'))
        post.assert_not_called()


class VentasTests(_ConCartolas):
    def test_ventas_cuadran_con_el_resumen(self):
        r = self.client.get(f'{self.base}/ventas/?anio=2026').data
        resumen = self.client.get(f'{self.base}/resumen/?anio=2026').data
        self.assertEqual(r['total'], resumen['ingresos'])
        self.assertEqual(sum(m['monto'] for m in r['meses']), r['total'])
        self.assertEqual(sum(x['monto'] for x in r['clientes']), r['total'])
        self.assertGreaterEqual(r['concentracion_top3'], r['concentracion_top1'])
        nc = sum(m['notas_credito'] for m in r['meses'])
        self.assertEqual(nc, 1)                                  # la nota de crédito no es factura


class HerramientaDocumentosTests(_ConCartolas):
    def test_cuenta_documentos_por_libro_y_contraparte(self):
        from apps.finanzas import herramienta
        org = self.org
        compras = herramienta.ejecutar(org, {'consulta': 'documentos', 'libro': 'compras', 'anio': 2026})
        self.assertEqual(compras['cantidad'], DocumentoTributario.objects.filter(organization=org, libro='compras').count())
        self.assertLessEqual(compras['detalle_de_los_mas_recientes'], herramienta.MAX_DOCUMENTOS)
        uno = compras['mas_recientes'][0]['contraparte']
        filtrado = herramienta.ejecutar(org, {'consulta': 'documentos', 'contraparte': uno[:8], 'anio': 2026})
        self.assertGreater(filtrado['cantidad'], 0)
        self.assertLess(filtrado['cantidad'], compras['cantidad'] + 100)

    def test_ventas_por_el_chat(self):
        from apps.finanzas import herramienta
        r = herramienta.ejecutar(self.org, {'consulta': 'ventas', 'anio': 2026})
        self.assertGreater(r['total'], 0)
        self.assertLessEqual(len(r['clientes']), 10)
