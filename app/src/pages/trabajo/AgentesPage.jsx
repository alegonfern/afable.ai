import { Box } from '@mui/material';
import PageHeader from '../../components/PageHeader';
import AgentesGaleria from './AgentesGaleria';

/**
 * Casa propia de la galería de Agentes.
 *
 * Antes la galería solo aparecía en la home de Trabajo y en el chat vacío, así
 * que al entrar a una conversación del historial desaparecía y no había forma
 * de volver a ella. Con esta pantalla la galería se alcanza siempre igual,
 * haya o no una conversación abierta.
 */
export default function AgentesPage() {
  return (
    <Box sx={{ display: 'flex', flexDirection: 'column', minHeight: '100%' }}>
      <PageHeader title="Agentes" back="/app" backLabel="Trabajo" />
      <AgentesGaleria />
    </Box>
  );
}
