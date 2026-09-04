import { useState, useEffect, useCallback } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  Box, Typography, Button, Chip, useTheme,
  Dialog, DialogTitle, DialogContent, DialogActions,
  TextField, IconButton, CircularProgress, Divider,
} from '@mui/material';
import { Database, Plus, Trash2, RefreshCw, CheckCircle, XCircle, Zap, FileText, X, Pencil } from 'lucide-react';
import { toast } from 'react-toastify';
import PageHeader from '../components/PageHeader';
import { api } from '../services/api';
import { logoDeServicio } from '../assets/logos';

// ── Definición de conectores disponibles ──────────────────────────────────────

const CONNECTORS = [
  {
    id: 'odoo',
    name: 'Odoo',
    label: 'ERP',
    category: 'erp',
    description: 'Conecta tu instancia de Odoo para acceder a ventas, inventario, contabilidad y más.',
    icon: '🟢',
    color: '#875A7B',
    fields: [
      { key: 'url',      label: 'URL de Odoo',       placeholder: 'https://miempresa.odoo.com', type: 'text' },
      { key: 'db',       label: 'Base de datos',      placeholder: 'miempresa',                  type: 'text' },
      { key: 'username', label: 'Usuario (email)',     placeholder: 'admin@miempresa.com',        type: 'email' },
      { key: 'api_key',  label: 'API Key',             placeholder: 'xxxxxxxxxxxxxxxx',           type: 'password' },
    ],
  },
  {
    id: 'mssql',
    name: 'SAP Business One',
    label: 'ERP',
    category: 'erp',
    description: 'Conexión directa a la base de SAP B1 (SQL Server). Cubre también cualquier ERP con base MSSQL.',
    icon: '🔷',
    color: '#CC2927',
    fields: [
      { key: 'host',     label: 'Host / IP',          placeholder: '192.168.1.100',              type: 'text' },
      { key: 'port',     label: 'Puerto',             placeholder: '1433',                        type: 'text' },
      { key: 'database', label: 'Base de datos',      placeholder: 'SBO_MIEMPRESA',              type: 'text' },
      { key: 'username', label: 'Usuario',            placeholder: 'sa',                          type: 'text' },
      { key: 'password', label: 'Contraseña',         placeholder: '••••••••',                   type: 'password' },
    ],
  },
  {
    id: 'postgresql',
    name: 'PostgreSQL',
    label: 'Base de datos',
    category: 'db',
    description: 'Conecta cualquier base de datos PostgreSQL para consultas directas desde el chat.',
    icon: '🐘',
    color: '#336791',
    fields: [
      { key: 'host',     label: 'Host / IP',          placeholder: 'localhost',                  type: 'text' },
      { key: 'port',     label: 'Puerto',             placeholder: '5432',                        type: 'text' },
      { key: 'database', label: 'Base de datos',      placeholder: 'mi_base',                    type: 'text' },
      { key: 'username', label: 'Usuario',            placeholder: 'postgres',                    type: 'text' },
      { key: 'password', label: 'Contraseña',         placeholder: '••••••••',                   type: 'password' },
    ],
  },
  {
    id: 'csv',
    name: 'Excel / CSV',
    label: 'Archivo',
    category: 'db',
    description: 'Sube un archivo Excel o CSV. El agente podrá responder preguntas sobre esos datos al instante.',
    icon: '📄',
    color: '#217346',
    fields: [],
    isFile: true,
  },
  {
    id: 'google_drive',
    name: 'Google Drive',
    label: 'Carpeta compartida',
    category: 'db',
    description: 'Elige los archivos de Drive que la IA puede leer. Se sincronizan solos cada 15 min y se actualizan cuando alguien los edita.',
    icon: '🔵',
    color: '#1FA463',
    fields: [],
    oauth: true,
  },
];

const CONNECTOR_MAP = Object.fromEntries(CONNECTORS.map(c => [c.id, c]));

/**
 * Icono de un conector. Usa el logo real del servicio cuando lo tenemos
 * (`assets/logos`, resuelto por el nombre del conector) y cae al emoji de
 * `connector.icon` para los que todavía no tienen logo.
 *
 * Va siempre sobre una baldosa blanca: las marcas están hechas para leerse
 * sobre blanco y la app tiene tema claro y oscuro. La baldosa también aplica
 * a los emojis, para que la lista no quede con dos tamaños de icono.
 */
function ConnectorIcon({ connector = {}, size = 36 }) {
  const logo = logoDeServicio(connector.name);
  return (
    <Box
      sx={{
        width: size, height: size, flexShrink: 0,
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        bgcolor: '#fff',
        border: '1px solid rgba(0,0,0,0.08)',
        borderRadius: '9px',
        p: logo ? '5px' : 0,
        fontSize: size * 0.5,
        lineHeight: 1,
        boxSizing: 'border-box',
      }}
    >
      {logo
        ? <Box component="img" src={logo} alt={connector.name}
            sx={{ maxWidth: '100%', maxHeight: '100%', objectFit: 'contain', display: 'block' }} />
        : (connector.icon || '🔌')}
    </Box>
  );
}

// Estructura de integraciones: ERP y CRM son integraciones profundas nativas;
// el resto del catálogo entra como conector (capa de automatización).
const SECTIONS = [
  { key: 'erp', title: 'ERP — Conexión profunda', soon: [] },
  { key: 'crm', title: 'CRM — Conexión profunda', soon: ['HubSpot', 'Salesforce'] },
  { key: 'db', title: 'Bases de datos y archivos', soon: [] },
];

const CONNECTOR_CATALOG_SOON = ['WhatsApp', 'Shopify', 'Slack', 'Google Sheets', 'Notion', 'Mercado Libre', '+300 más'];

const CATEGORY_CHIP = { erp: 'ERP', crm: 'CRM', db: 'BD' };

// ── Modal para agregar conexión ───────────────────────────────────────────────

function ConnectModal({ open, connector, orgId, existingConn, onClose, onCreated }) {
  const theme = useTheme();
  const isEdit = !!existingConn;
  const [name, setName] = useState('');
  const [config, setConfig] = useState({});
  const [testing, setTesting] = useState(false);
  const [saving, setSaving] = useState(false);
  const [testResult, setTestResult] = useState(null);

  useEffect(() => {
    if (open) {
      setName(existingConn?.name || connector?.name || '');
      setConfig({});
      setTestResult(null);
    }
  }, [open, connector, existingConn]);

  if (!connector) return null;

  const setField = (key, value) => {
    setConfig(p => ({ ...p, [key]: value }));
    setTestResult(null);
  };

  const handleTest = async () => {
    setTesting(true);
    setTestResult(null);
    try {
      // Crear conexión temporal para test
      const res = await api.createConnection({
        organization: orgId,
        name: name || `${connector.name} Test`,
        connector_type: connector.id,
        category: connector.category || 'otro',
        config,
      });
      const testRes = await api.testConnection(res.data.id);
      setTestResult(testRes.data);
      if (!testRes.data.success) {
        await api.descartarConnectionDePrueba(res.data.id);
      } else {
        // Si fue exitoso, guarda el id para no re-crear
        setConfig(p => ({ ...p, _tmp_id: res.data.id }));
      }
    } catch (e) {
      setTestResult({ success: false, error: e.response?.data?.detail || 'Error de conexión' });
    } finally {
      setTesting(false);
    }
  };

  const handleSave = async () => {
    if (!name.trim()) { toast.error('Ingresa un nombre para esta conexión'); return; }
    setSaving(true);
    try {
      if (isEdit) {
        // Solo manda los campos que el usuario efectivamente tocó — el backend
        // hace merge, así que los que quedaron en blanco no se tocan.
        const { _tmp_id, ...typedFields } = config;
        await api.updateConnection(existingConn.id, { name, config: typedFields });
        onCreated();
        onClose();
        toast.success(`${connector.name} actualizado`);
        return;
      }

      let connId = config._tmp_id;
      if (connId) {
        // Ya fue creado en el test, solo actualizamos el nombre
        await api.updateConnection(connId, { name });
        onCreated();
        onClose();
      } else {
        await api.createConnection({
          organization: orgId,
          name,
          connector_type: connector.id,
          category: connector.category || 'otro',
          config,
        });
        onCreated();
        onClose();
      }
      toast.success(`${connector.name} conectado`);
    } catch (e) {
      toast.error(e.response?.data?.detail || 'Error al guardar conexión');
    } finally {
      setSaving(false);
    }
  };

  const inputSx = {
    '& .MuiOutlinedInput-root': {
      fontSize: '0.85rem',
      '& fieldset': { borderColor: theme.palette.divider },
      '&:hover fieldset': { borderColor: 'rgba(88, 106, 208,0.4)' },
      '&.Mui-focused fieldset': { borderColor: '#586AD0' },
    },
    '& .MuiInputLabel-root': { fontSize: '0.82rem' },
    '& .MuiInputLabel-root.Mui-focused': { color: '#586AD0' },
  };

  return (
    <Dialog
      open={open}
      onClose={onClose}
      maxWidth="sm"
      fullWidth
      PaperProps={{
        sx: {
          bgcolor: 'background.paper',
          border: `1px solid ${theme.palette.divider}`,
          borderRadius: '12px',
          backgroundImage: 'none',
        },
      }}
    >
      <DialogTitle sx={{ pb: 1, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.5 }}>
          <ConnectorIcon connector={connector} size={34} />
          <Box>
            <Typography sx={{ fontWeight: 600, fontSize: '0.95rem', color: 'text.primary' }}>
              {isEdit ? `Editar ${connector.name}` : `Conectar ${connector.name}`}
            </Typography>
            <Typography sx={{ fontSize: '0.75rem', color: 'text.disabled' }}>{connector.label}</Typography>
          </Box>
        </Box>
        <IconButton size="small" onClick={onClose} sx={{ color: 'text.disabled' }}>
          <X size={16} />
        </IconButton>
      </DialogTitle>

      <Divider />

      <DialogContent sx={{ pt: 2.5, pb: 1, display: 'flex', flexDirection: 'column', gap: 2 }}>
        <TextField
          label="Nombre de esta conexión"
          placeholder={`${connector.name} Producción`}
          value={name}
          onChange={e => setName(e.target.value)}
          fullWidth
          size="small"
          sx={inputSx}
        />

        {isEdit && (
          <Typography sx={{ fontSize: '0.75rem', color: 'text.disabled', mt: -1 }}>
            Por seguridad no mostramos las credenciales guardadas — deja en blanco lo que no quieras cambiar.
          </Typography>
        )}

        {connector.fields.map(f => (
          <TextField
            key={f.key}
            label={f.label}
            placeholder={isEdit ? '•••• (sin cambios)' : f.placeholder}
            type={f.type}
            value={config[f.key] || ''}
            onChange={e => setField(f.key, e.target.value)}
            fullWidth
            size="small"
            sx={inputSx}
          />
        ))}

        {connector.isFile && (
          <Box sx={{
            border: `2px dashed ${theme.palette.divider}`,
            borderRadius: '8px', p: 3,
            display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 1,
            color: 'text.disabled', cursor: 'pointer',
            '&:hover': { borderColor: 'rgba(88, 106, 208,0.4)', color: 'text.secondary' },
          }}>
            <FileText size={24} />
            <Typography sx={{ fontSize: '0.82rem' }}>Arrastra tu archivo aquí o haz clic</Typography>
            <Typography sx={{ fontSize: '0.72rem' }}>Excel (.xlsx) o CSV — máximo 10MB</Typography>
          </Box>
        )}

        {testResult && (
          <Box sx={{
            display: 'flex', alignItems: 'center', gap: 1, p: 1.5,
            borderRadius: '8px',
            bgcolor: testResult.success ? 'rgba(52,211,153,0.08)' : 'rgba(239,68,68,0.08)',
            border: `1px solid ${testResult.success ? 'rgba(52,211,153,0.25)' : 'rgba(239,68,68,0.25)'}`,
          }}>
            {testResult.success
              ? <CheckCircle size={15} color="#34D399" />
              : <XCircle size={15} color="#f87171" />}
            <Typography sx={{ fontSize: '0.8rem', color: testResult.success ? '#34D399' : '#f87171' }}>
              {testResult.success
                ? `Conexión exitosa${testResult.tables_count ? ` — ${testResult.tables_count} tablas encontradas` : ''}`
                : testResult.error || 'Error de conexión'}
            </Typography>
          </Box>
        )}
      </DialogContent>

      <DialogActions sx={{ px: 3, pb: 2.5, pt: 1.5, gap: 1 }}>
        {!connector.isFile && !isEdit && (
          <Button
            onClick={handleTest}
            disabled={testing || saving}
            startIcon={testing ? <CircularProgress size={12} /> : <Zap size={13} />}
            sx={{
              fontSize: '0.78rem', color: 'text.secondary',
              border: `1px solid ${theme.palette.divider}`,
              borderRadius: '7px', px: 1.5,
              '&:hover': { borderColor: 'rgba(88, 106, 208,0.3)', color: '#9BA6E3' },
            }}
          >
            {testing ? 'Probando...' : 'Probar conexión'}
          </Button>
        )}
        <Box sx={{ flex: 1 }} />
        <Button onClick={onClose} sx={{ fontSize: '0.78rem', color: 'text.secondary' }}>
          Cancelar
        </Button>
        <Button
          onClick={handleSave}
          disabled={saving || !name.trim()}
          variant="contained"
          startIcon={saving ? <CircularProgress size={12} color="inherit" /> : null}
          sx={{
            fontSize: '0.78rem', fontWeight: 600,
            bgcolor: '#586AD0', borderRadius: '7px',
            '&:hover': { bgcolor: '#2F42A6' },
            '&.Mui-disabled': { bgcolor: 'action.disabledBackground' },
          }}
        >
          {saving ? 'Guardando...' : (isEdit ? 'Guardar cambios' : 'Guardar conexión')}
        </Button>
      </DialogActions>
    </Dialog>
  );
}

// ── Fila de sistema conectado ─────────────────────────────────────────────────

function ConnectedRow({ conn, onDeleted, onSynced, onEdit }) {
  const theme = useTheme();
  const connector = CONNECTOR_MAP[conn.connector_type] || {};
  const [testing, setTesting] = useState(false);
  const [syncing, setSyncing] = useState(false);
  const [testOk, setTestOk] = useState(null);

  const handleTest = async () => {
    setTesting(true);
    setTestOk(null);
    try {
      const res = await api.testConnection(conn.id);
      setTestOk(res.data.success);
      if (res.data.success) toast.success('Conexión activa');
      else toast.error(res.data.error || 'Conexión fallida');
    } catch {
      setTestOk(false);
      toast.error('Error al probar conexión');
    } finally {
      setTesting(false);
    }
  };

  const handleSync = async () => {
    setSyncing(true);
    try {
      const { data } = await api.syncConnection(conn.id);
      if (isDrive) {
        // Para Drive lo que importa es cuantos documentos quedaron disponibles,
        // no que la llamada haya respondido 200.
        const n = data.documentos || 0;
        if (n > 0) toast.success(`${n} documento${n === 1 ? '' : 's'} al día`);
        else toast.warning('Google no entregó el contenido de lo que elegiste. Vuelve a elegir los archivos.');
      } else {
        toast.success('Esquema sincronizado');
      }
      onSynced();
    } catch {
      toast.error('No se pudo actualizar la fuente.');
    } finally {
      setSyncing(false);
    }
  };

  const handleDelete = async () => {
    try {
      await api.desactivarConnection(conn.id);
      toast.info('Conexión desactivada. Lo que trajo se queda.');
      onDeleted(conn.id);
    } catch {
      toast.error('No se pudo desactivar');
    }
  };

  const lastSync = conn.last_synced_at
    ? new Date(conn.last_synced_at).toLocaleDateString('es', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' })
    : null;

  const isDrive = conn.connector_type === 'google_drive';
  const canEdit = (connector.fields?.length || 0) > 0;
  const tableCount = conn.schema_cache?.tables?.length || conn.schema_cache?.models?.length || null;
  const driveFileCount = isDrive ? Object.keys(conn.schema_cache?.files || {}).length : null;

  return (
    <Box sx={{
      display: 'flex', alignItems: 'center', gap: 2,
      p: 2, borderRadius: '10px',
      bgcolor: 'background.paper',
      border: `1px solid ${theme.palette.divider}`,
      borderLeft: `3px solid ${testOk === false ? '#f87171' : '#34D399'}`,
      transition: 'border-color 0.2s',
    }}>
      <ConnectorIcon connector={connector} size={34} />

      <Box sx={{ flex: 1, minWidth: 0 }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1, mb: 0.25 }}>
          <Typography sx={{ fontWeight: 600, fontSize: '0.88rem', color: 'text.primary' }}>
            {conn.name}
          </Typography>
          {CATEGORY_CHIP[conn.category] && (
            <Chip
              label={CATEGORY_CHIP[conn.category]}
              size="small"
              sx={{ height: 17, fontSize: '0.64rem', fontWeight: 700, letterSpacing: '0.04em', bgcolor: 'rgba(124,58,237,0.1)', color: '#9BA6E3', border: '1px solid rgba(124,58,237,0.3)', '& .MuiChip-label': { px: 0.75 } }}
            />
          )}
          <Chip
            label={connector.name || conn.connector_type}
            size="small"
            sx={{ height: 17, fontSize: '0.66rem', fontWeight: 500, bgcolor: 'action.hover', color: 'text.secondary', border: `1px solid ${theme.palette.divider}`, '& .MuiChip-label': { px: 0.75 } }}
          />
          {testOk === true && <CheckCircle size={13} color="#34D399" />}
          {testOk === false && <XCircle size={13} color="#f87171" />}
        </Box>
        <Typography sx={{ fontSize: '0.72rem', color: 'text.disabled' }}>
          {isDrive
            ? `${conn.drive_seleccion ? `${conn.drive_seleccion} · ` : ''}${
                !lastSync
                  ? 'sin sincronizar todavía'
                  : conn.drive_documentos
                    ? `sync ${lastSync} · ${conn.drive_documentos} documento${conn.drive_documentos === 1 ? '' : 's'}`
                    : `sync ${lastSync} · Google no entrega el contenido de lo elegido`
              }`
            : (lastSync ? `Sincronizado ${lastSync}` : 'Sin sincronizar')}
          {tableCount ? ` · ${tableCount} ${conn.schema_cache?.models ? 'módulos' : 'tablas'}` : ''}
          {driveFileCount ? ` · ${driveFileCount} archivo${driveFileCount === 1 ? '' : 's'}` : ''}
        </Typography>
      </Box>

      <Box sx={{ display: 'flex', gap: 0.75, flexShrink: 0 }}>
        {!isDrive && (
          <Button
            size="small"
            onClick={handleTest}
            disabled={testing}
            startIcon={testing ? <CircularProgress size={11} /> : <Zap size={12} />}
            sx={{ fontSize: '0.72rem', color: 'text.secondary', border: `1px solid ${theme.palette.divider}`, borderRadius: '6px', px: 1, minWidth: 0, '&:hover': { borderColor: 'rgba(88, 106, 208,0.3)', color: '#9BA6E3' } }}
          >
            {testing ? '...' : 'Probar'}
          </Button>
        )}
        <Button
          size="small"
          onClick={handleSync}
          disabled={syncing}
          title={isDrive
            ? 'Vuelve a leer los archivos ahora, sin esperar la sincronización automática'
            : 'Vuelve a leer el esquema de este sistema'}
          startIcon={syncing ? <CircularProgress size={11} /> : <RefreshCw size={12} />}
          sx={{ fontSize: '0.72rem', color: 'text.secondary', border: `1px solid ${theme.palette.divider}`, borderRadius: '6px', px: 1, minWidth: 0, '&:hover': { borderColor: 'rgba(88, 106, 208,0.3)', color: '#9BA6E3' } }}
        >
          {syncing ? '...' : 'Actualizar'}
        </Button>
        {canEdit && (
          <IconButton size="small" onClick={() => onEdit(conn)} sx={{ color: 'text.disabled', '&:hover': { color: '#9BA6E3', bgcolor: 'rgba(88, 106, 208,0.08)' } }}>
            <Pencil size={14} />
          </IconButton>
        )}
        <IconButton size="small" onClick={handleDelete} sx={{ color: 'text.disabled', '&:hover': { color: '#f87171', bgcolor: 'rgba(239,68,68,0.08)' } }}>
          <Trash2 size={14} />
        </IconButton>
      </Box>
    </Box>
  );
}

// ── Card de conector disponible ───────────────────────────────────────────────

function ConnectorCard({ connector, onClick }) {
  const theme = useTheme();
  const [hover, setHover] = useState(false);

  return (
    <Box
      onClick={onClick}
      onMouseEnter={() => setHover(true)}
      onMouseLeave={() => setHover(false)}
      sx={{
        display: 'flex', flexDirection: 'column', gap: 1.5,
        p: 2.5, borderRadius: '10px', cursor: 'pointer',
        bgcolor: hover ? 'rgba(88, 106, 208,0.04)' : 'background.paper',
        border: `1px solid ${hover ? 'rgba(88, 106, 208,0.3)' : theme.palette.divider}`,
        transition: 'all 0.15s',
      }}
    >
      <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 1.25 }}>
          <ConnectorIcon connector={connector} size={38} />
          <Box>
            <Typography sx={{ fontWeight: 600, fontSize: '0.88rem', color: 'text.primary' }}>
              {connector.name}
            </Typography>
            <Typography sx={{ fontSize: '0.7rem', color: 'text.disabled' }}>{connector.label}</Typography>
          </Box>
        </Box>
        <Box sx={{
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          width: 26, height: 26, borderRadius: '6px',
          bgcolor: hover ? 'rgba(88, 106, 208,0.12)' : 'action.hover',
          transition: 'all 0.15s',
        }}>
          <Plus size={14} color={hover ? '#9BA6E3' : theme.palette.text.disabled} />
        </Box>
      </Box>
      <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary', lineHeight: 1.6 }}>
        {connector.description}
      </Typography>
    </Box>
  );
}

// ── Google Picker (elegir carpeta) ────────────────────────────────────────────
let _pickerScriptPromise = null;

function loadGooglePicker() {
  if (window.google?.picker) return Promise.resolve();
  if (!_pickerScriptPromise) {
    _pickerScriptPromise = new Promise((resolve, reject) => {
      const script = document.createElement('script');
      script.src = 'https://apis.google.com/js/api.js';
      script.onload = () => window.gapi.load('picker', resolve);
      script.onerror = reject;
      document.body.appendChild(script);
    });
  }
  return _pickerScriptPromise;
}

/**
 * Selector de Drive: se eligen ARCHIVOS, y se pueden elegir varios.
 *
 * Antes pedia `ViewId.FOLDERS` y solo mostraba carpetas. Eso no funciona con el
 * permiso que tenemos (`drive.file`), que autoriza unicamente los archivos que el
 * usuario elige uno por uno: al elegir una carpeta, Google devuelve su contenido
 * vacio y la sincronizacion no trae nada. Con archivos si entrega el contenido.
 * El dia que se pase a `drive.readonly` se puede volver a ofrecer la carpeta.
 */
async function openDrivePicker(accessToken, appId, onPicked) {
  await loadGooglePicker();
  const vista = new window.google.picker.DocsView(window.google.picker.ViewId.DOCS)
    .setIncludeFolders(true)        // se puede navegar dentro de las carpetas...
    .setSelectFolderEnabled(false); // ...pero lo que se elige son los archivos
  const picker = new window.google.picker.PickerBuilder()
    .setOAuthToken(accessToken)
    .setDeveloperKey(import.meta.env.VITE_GOOGLE_API_KEY || '')
    // Sin setAppId, los archivos elegidos NO quedan autorizados para esta app:
    // Google responde 404 al leerlos, aunque el usuario los haya elegido.
    .setAppId(appId || '')
    .enableFeature(window.google.picker.Feature.MULTISELECT_ENABLED)
    .addView(vista)
    .setTitle('Elige los archivos que Afable puede leer')
    .setCallback((data) => {
      if (data.action === window.google.picker.Action.PICKED) {
        onPicked((data.docs || []).map((d) => ({ id: d.id, name: d.name })));
      }
    })
    .build();
  picker.setVisible(true);
}

// ── Página principal ──────────────────────────────────────────────────────────

export default function IntegrationsPage({ hideHeader = false }) {
  const theme = useTheme();
  const [searchParams, setSearchParams] = useSearchParams();
  const [connections, setConnections] = useState([]);
  const [orgId, setOrgId] = useState(null);
  const [modalConnector, setModalConnector] = useState(null);
  const [editingConn, setEditingConn] = useState(null);
  const [loading, setLoading] = useState(true);
  const [requestOpen, setRequestOpen] = useState(false);
  const [requestText, setRequestText] = useState('');
  const [requestSending, setRequestSending] = useState(false);
  const [connectingDrive, setConnectingDrive] = useState(false);

  const submitRequest = async () => {
    if (!requestText.trim()) return;
    setRequestSending(true);
    try {
      await api.requestIntegration({ description: requestText.trim() });
      toast.success('Solicitud enviada — te avisamos cuando esté disponible.');
      setRequestOpen(false);
      setRequestText('');
    } catch {
      toast.error('No se pudo enviar la solicitud, intenta de nuevo.');
    } finally {
      setRequestSending(false);
    }
  };

  const load = async () => {
    try {
      const [connsRes, orgsRes] = await Promise.all([
        api.getConnections(),
        api.getOrganizations(),
      ]);
      setConnections(connsRes.data);
      const org = orgsRes.data.find(o => o.nombre !== 'Personal') || orgsRes.data[0];
      if (org) setOrgId(org.id);
    } catch {
      toast.error('Error al cargar conexiones');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => { load(); }, []);

  // Vuelta del OAuth de Drive (ver GoogleDriveConnectCallbackView en el backend):
  // llegamos con ?drive_connection_id=X y falta el paso 3, elegir la carpeta con el Picker.
  useEffect(() => {
    const connId = searchParams.get('drive_connection_id');
    const driveError = searchParams.get('drive_error');
    if (driveError) {
      toast.error('No se pudo conectar Google Drive. Intenta de nuevo.');
      setSearchParams(p => { p.delete('drive_error'); return p; }, { replace: true });
      return;
    }
    if (!connId) return;
    setSearchParams(p => { p.delete('drive_connection_id'); return p; }, { replace: true });

    (async () => {
      setConnectingDrive(true);
      try {
        const { data } = await api.getDriveAccessToken(connId);
        await openDrivePicker(data.access_token, data.app_id, async (archivos) => {
          try {
            const res = await api.saveDriveFiles(connId, archivos);
            const n = res.data.documentos || 0;
            if (n > 0) {
              toast.success(`${n} documento${n === 1 ? '' : 's'} de Drive ya disponible${n === 1 ? '' : 's'} para la IA`);
            } else {
              toast.warning('Los archivos quedaron enlazados, pero Drive no entregó su contenido.');
            }
            load();
          } catch {
            toast.error('No se pudieron guardar los archivos elegidos.');
          }
        });
      } catch {
        toast.error('No se pudo abrir el selector de archivos de Drive.');
      } finally {
        setConnectingDrive(false);
      }
    })();
  }, [searchParams]);

  const handleConnectorClick = useCallback(async (connector) => {
    if (!orgId) return;
    if (connector.id === 'google_drive') {
      setConnectingDrive(true);
      try {
        const { data } = await api.startGoogleDriveConnect();
        window.location.href = data.auth_url;
      } catch {
        toast.error('No se pudo iniciar la conexión con Google Drive.');
        setConnectingDrive(false);
      }
      return;
    }
    setModalConnector(connector);
  }, [orgId]);

  const sectionLabel = {
    fontSize: '0.7rem', fontWeight: 600,
    color: 'text.disabled', letterSpacing: '0.08em',
    textTransform: 'uppercase', mb: 1.5,
  };

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100%' }}>
      {!hideHeader && <PageHeader title="Conexiones" back="/app" backLabel="Inicio" />}

      <Box sx={{ pt: 2.5, pb: 5, px: { xs: 2, sm: 3 }, maxWidth: 860, width: '100%' }}>

        {/* Sistemas conectados */}
        {(loading || connections.length > 0) && (
          <Box sx={{ mb: 4 }}>
            <Typography sx={sectionLabel}>Sistemas conectados</Typography>
            {loading ? (
              <Box sx={{ display: 'flex', justifyContent: 'center', py: 4 }}>
                <CircularProgress size={24} sx={{ color: '#586AD0' }} />
              </Box>
            ) : (
              <Box sx={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
                {connections.map(conn => (
                  <ConnectedRow
                    key={conn.id}
                    conn={conn}
                    onDeleted={(id) => setConnections(p => p.filter(c => c.id !== id))}
                    onSynced={load}
                    onEdit={setEditingConn}
                  />
                ))}
              </Box>
            )}
          </Box>
        )}

        {/* Conectores disponibles */}
        <Box>
          <Box sx={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', mb: 1.5 }}>
            <Typography sx={sectionLabel}>Agregar sistema</Typography>
          </Box>

          {!orgId && !loading && (
            <Box sx={{
              p: 2.5, borderRadius: '10px', mb: 2,
              bgcolor: 'rgba(251,191,36,0.06)',
              border: '1px solid rgba(251,191,36,0.2)',
            }}>
              <Typography sx={{ fontSize: '0.82rem', color: 'text.secondary' }}>
                Primero crea tu empresa en el chat antes de conectar sistemas. Escribe en el chat: <strong>"Crear empresa [nombre]"</strong>.
              </Typography>
            </Box>
          )}

          {SECTIONS.map(section => {
            const items = CONNECTORS.filter(c => c.category === section.key);
            if (!items.length && !section.soon.length) return null;
            return (
              <Box key={section.key} sx={{ mb: 3 }}>
                <Typography sx={{ ...sectionLabel, mb: 1, fontSize: '0.66rem' }}>{section.title}</Typography>
                {items.length > 0 && (
                  <Box sx={{ display: 'grid', gridTemplateColumns: { xs: '1fr', sm: '1fr 1fr' }, gap: 1.5 }}>
                    {items.map(c => (
                      <ConnectorCard
                        key={c.id}
                        connector={c}
                        onClick={() => handleConnectorClick(c)}
                      />
                    ))}
                  </Box>
                )}
                {section.soon.length > 0 && (
                  <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1, mt: items.length ? 1.5 : 0 }}>
                    {section.soon.map(name => (
                      <Chip
                        key={name}
                        label={`${name} · próximamente`}
                        size="small"
                        sx={{ fontSize: '0.75rem', bgcolor: 'action.hover', color: 'text.disabled', border: `1px solid ${theme.palette.divider}`, '& .MuiChip-label': { px: 1.25 } }}
                      />
                    ))}
                  </Box>
                )}
              </Box>
            );
          })}
        </Box>

        {/* Conectores — catálogo vía capa de automatización */}
        <Box sx={{ mt: 1 }}>
          <Typography sx={{ ...sectionLabel, mb: 1 }}>Conectores</Typography>
          <Typography sx={{ fontSize: '0.78rem', color: 'text.secondary', mb: 1.25 }}>
            Acciones y automatizaciones con las demás herramientas que usas — próximamente.
          </Typography>
          <Box sx={{ display: 'flex', flexWrap: 'wrap', gap: 1 }}>
            {CONNECTOR_CATALOG_SOON.map(name => (
              <Chip
                key={name}
                label={name}
                size="small"
                sx={{ fontSize: '0.75rem', bgcolor: 'action.hover', color: 'text.disabled', border: `1px solid ${theme.palette.divider}`, '& .MuiChip-label': { px: 1.25 } }}
              />
            ))}
          </Box>
        </Box>

        {/* Solicitar una integración que no está en el catálogo */}
        <Box sx={{ mt: 3, pt: 2.5, borderTop: `1px solid ${theme.palette.divider}` }}>
          <Typography sx={{ fontSize: '0.85rem', color: 'text.secondary', mb: 1 }}>
            ¿No encuentras el sistema que usas?
          </Typography>
          <Button
            size="small" variant="outlined" startIcon={<Plus size={14} />}
            onClick={() => setRequestOpen(true)}
            sx={{ textTransform: 'none', fontSize: '0.8rem' }}
          >
            Solicitar conexión
          </Button>
        </Box>
      </Box>

      <ConnectModal
        open={!!modalConnector}
        connector={modalConnector}
        orgId={orgId}
        onClose={() => setModalConnector(null)}
        onCreated={() => { setModalConnector(null); load(); }}
      />

      <ConnectModal
        open={!!editingConn}
        connector={editingConn ? CONNECTOR_MAP[editingConn.connector_type] : null}
        existingConn={editingConn}
        orgId={orgId}
        onClose={() => setEditingConn(null)}
        onCreated={() => { setEditingConn(null); load(); }}
      />

      <Dialog open={requestOpen} onClose={() => setRequestOpen(false)} maxWidth="sm" fullWidth>
        <DialogTitle sx={{ fontSize: '1rem', fontWeight: 600 }}>Solicitar conexión</DialogTitle>
        <DialogContent>
          <Typography sx={{ fontSize: '0.82rem', color: 'text.secondary', mb: 2 }}>
            Contanos qué sistema querés conectar — le llega directo a nuestro equipo.
          </Typography>
          <TextField
            autoFocus fullWidth multiline minRows={3} maxRows={8}
            placeholder="Ej: usamos Bsale para facturación, nos gustaría conectarlo para..."
            value={requestText}
            onChange={(e) => setRequestText(e.target.value)}
          />
        </DialogContent>
        <DialogActions sx={{ px: 3, pb: 2.5 }}>
          <Button onClick={() => setRequestOpen(false)} sx={{ textTransform: 'none' }}>Cancelar</Button>
          <Button
            variant="contained" onClick={submitRequest}
            disabled={requestSending || !requestText.trim()}
            sx={{ textTransform: 'none' }}
          >
            {requestSending ? <CircularProgress size={16} sx={{ color: '#fff' }} /> : 'Enviar solicitud'}
          </Button>
        </DialogActions>
      </Dialog>
    </Box>
  );
}
