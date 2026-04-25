import { Box, Container, Button, Typography } from "@mui/material";
import { Logout, AutoAwesome } from "@mui/icons-material";
import { Toaster } from 'react-hot-toast';

const styles = {
  container: {
    background: 'linear-gradient(135deg, #F0F7FF 0%, #E8F2FF 100%)',
    minHeight: '100vh',
    py: 4
  },
  mainCard: {
    backgroundColor: 'white',
    borderRadius: '24px',
    boxShadow: '0 10px 30px rgba(0, 0, 0, 0.05)',
    overflow: 'hidden',
    p: 0,
    position: 'relative'
  },
  header: {
    background: 'linear-gradient(to right, #F8FAFC, #EFF6FF)',
    p: 3,
    borderBottom: '1px solid rgba(0, 0, 0, 0.05)'
  }
};

export default function Layout({ children, onLogout }) {
  return (
    <Box sx={styles.container}>
      <Toaster position="top-right" />
      <Container maxWidth="lg">
        <Box sx={styles.mainCard}>
          <Box sx={styles.header}>
            <Box sx={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
                <AutoAwesome sx={{ color: '#3B82F6', fontSize: 32 }} />
                <Box>
                  <Typography variant="h5" sx={{ color: '#1E293B', fontWeight: 600 }}>
                    Devanagari Text Detection
                  </Typography>
                  <Typography variant="body2" sx={{ color: '#64748B' }}>
                    AI-Powered Text Recognition System
                  </Typography>
                </Box>
              </Box>
              <Button
                variant="outlined"
                onClick={onLogout}
                startIcon={<Logout />}
                sx={{ 
                  color: '#64748B',
                  borderColor: '#E2E8F0',
                  '&:hover': {
                    borderColor: '#94A3B8',
                    backgroundColor: '#F8FAFC'
                  }
                }}
              >
                Logout
              </Button>
            </Box>
          </Box>
          {children}
        </Box>
      </Container>
    </Box>
  );
}