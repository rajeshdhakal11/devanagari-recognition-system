import { motion } from 'framer-motion';
import { CircularProgress } from '@mui/material';
import CheckCircleOutline from '@mui/icons-material/CheckCircleOutline';

export const UploadProgressBar = ({ progress }) => (
  <motion.div
    key={progress}
    initial={{ width: 0 }}
    animate={{ width: `${progress}%` }}
    transition={{ duration: 0.5, ease: 'easeOut' }}
    style={{ height: 6, background: '#3B82F6', borderRadius: 3 }}
  />
);

export const ProcessingAnimation = ({ stepMessage }) => (
  <motion.div
    key={stepMessage}
    initial={{ opacity: 0, y: -10 }}
    animate={{ opacity: 1, y: 0 }}
    exit={{ opacity: 0, y: 10 }}
    transition={{ duration: 0.5 }}
  >
    <CircularProgress size={24} sx={{ color: '#64748B', mr: 1 }} />
    <span>{stepMessage}</span>
  </motion.div>
);

export const SuccessAnimation = () => (
  <motion.div
    initial={{ scale: 0 }}
    animate={{ scale: 1.2 }}
    transition={{ type: 'spring', stiffness: 200, damping: 10 }}
    style={{ display: 'flex', alignItems: 'center', gap: 8 }}
  >
    <CheckCircleOutline sx={{ fontSize: 50, color: '#10B981' }} />
    <span>Detection Complete!</span>
  </motion.div>
);
