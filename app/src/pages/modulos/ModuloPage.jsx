import PropTypes from 'prop-types';
import { useNavigate } from 'react-router-dom';
import { Box, Typography, useTheme } from '@mui/material';
import { Calculator, MessageSquare, ShoppingCart, Wallet, Zap } from 'lucide-react';
import PageHeader from '../../components/PageHeader';
import { tonoModulo } from '../../theme/tonos';

// Lo que va en cada página, con las tareas que nombró Alexis el 14-10-2026. Las pantallas
// todavía no existen: el texto dice qué viene y el chat queda como el lugar donde ya se
// puede pedir.
const MODULOS = {
  ventas: {
    label: 'Ventas',
    icon: ShoppingCart,
    modulo: 'Aquí va a trabajar las ventas de la empresa: facturar y revisar lo vendido.',
    automatizacion: 'Aquí va a ver y crear lo que Afable hace solo con las ventas, como '
      + 'facturar sin que nadie lo pida.',
  },
  contabilidad: {
    label: 'Contabilidad',
    icon: Calculator,
    modulo: 'Aquí va a trabajar la contabilidad de la empresa: conciliación, análisis, '
      + 'reportes y F29.',
    automatizacion: 'Aquí va a ver y crear lo que Afable hace solo con la contabilidad, como '
      + 'conciliar o preparar el F29.',
  },
  finanzas: {
    label: 'Finanzas',
    icon: Wallet,
    modulo: 'Aquí va a ver la plata de la empresa: caja, cuánto puede retirar, quién le debe y '
      + 'a quién le debe.',
    automatizacion: 'Aquí va a ver y crear lo que Afable hace solo con las finanzas, como avisar '
      + 'los cobros vencidos o si la caja se va a quedar corta.',
  },
};

/**
 * La página de un módulo, en sus dos posiciones del selector de la barra.
 *
 * Una sola pantalla para las cuatro rutas (Ventas y Contabilidad, cada una como Módulo o
 * como Automatización): cambia el título y el texto, y el encabezado dice a cuál se entró.
 */
export default function ModuloPage({ modulo, vista }) {
  const theme = useTheme();
  const navigate = useNavigate();
  const m = MODULOS[modulo];
  const enAutomatizacion = vista === 'automatizacion';
  const Icono = enAutomatizacion ? Zap : m.icon;

  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <PageHeader
        title={enAutomatizacion ? `${m.label} · Automatizaciones` : m.label}
        back="/app"
        backLabel="Inicio"
      />

      <Box sx={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', p: 3 }}>
        <Box sx={{ maxWidth: 440, textAlign: 'center' }}>
          <Box sx={{
            width: 44, height: 44, borderRadius: '10px', mx: 'auto', mb: 2,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            bgcolor: tonoModulo(modulo).suave,
            color: tonoModulo(modulo).color,
          }}>
            <Icono size={20} />
          </Box>
          <Typography sx={{ fontSize: '1.05rem', fontWeight: 600, mb: 1 }}>
            {enAutomatizacion ? `Automatizaciones de ${m.label}` : m.label}
          </Typography>
          <Typography sx={{ fontSize: '0.9rem', color: 'text.secondary', lineHeight: 1.6, mb: 2.5 }}>
            {enAutomatizacion ? m.automatizacion : m.modulo}
          </Typography>
          <Box
            component="button"
            onClick={() => navigate('/app/chat')}
            sx={{
              display: 'inline-flex', alignItems: 'center', gap: 0.75,
              px: 1.75, py: 0.75, borderRadius: '6px', cursor: 'pointer',
              border: `1px solid ${theme.palette.divider}`, bgcolor: 'transparent',
              fontFamily: 'inherit', fontSize: '0.85rem', color: 'text.primary',
              '&:hover': { bgcolor: theme.palette.action.hover },
              transition: 'background 0.12s',
            }}
          >
            <MessageSquare size={14} /> Pedirlo en el chat
          </Box>
        </Box>
      </Box>
    </Box>
  );
}

ModuloPage.propTypes = {
  modulo: PropTypes.oneOf(Object.keys(MODULOS)).isRequired,
  vista: PropTypes.oneOf(['modulo', 'automatizacion']).isRequired,
};
