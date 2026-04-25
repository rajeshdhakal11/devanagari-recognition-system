// ImageUploader.jsx
import { Box, Button, Typography, LinearProgress, CircularProgress } from "@mui/material";
import { Image as ImageIcon, UploadFile, CheckCircleOutline } from "@mui/icons-material";
import { useDropzone } from 'react-dropzone';
import { motion, AnimatePresence } from "framer-motion";

const styles = {
 uploadArea: {
   p: 4,
   display: 'flex',
   flexDirection: 'column',
   gap: 3
 },
 dropzone: {
   border: '2px dashed #E2E8F0',
   borderRadius: 16,
   p: 4,
   textAlign: 'center',
   cursor: 'pointer',
   backgroundColor: '#F8FAFC',
   transition: 'all 0.3s ease',
   display: 'flex',
   flexDirection: 'column',
   alignItems: 'center',
   justifyContent: 'center',
   minHeight: 250,
   position: 'relative',
   '&:hover': {
     borderColor: '#94A3B8',
     backgroundColor: '#F1F5F9',
     transform: 'translateY(-2px)'
   }
 },
 processButton: {
   backgroundColor: '#3B82F6',
   color: 'white',
   py: 2,
   px: 4,
   borderRadius: '12px',
   textTransform: 'none',
   fontSize: '1rem',
   fontWeight: 600,
   '&:hover': {
     backgroundColor: '#2563EB'
   },
   '&.Mui-disabled': {
     backgroundColor: '#94A3B8'  
   }
 }
};

export default function ImageUploader({ 
 onDrop, 
 file, 
 uploadProgress, 
 loading, 
 processingStep,
 onProcess,
 processingStates 
}) {
 const { getRootProps, getInputProps, isDragActive } = useDropzone({
   onDrop,
   accept: { 'image/*': ['.png', '.jpg', '.jpeg'] },
   maxSize: 10485760,
   maxFiles: 1
 });

 return (
   <Box sx={styles.uploadArea}>
     <Box
       {...getRootProps()}
       sx={{
         ...styles.dropzone,
         borderColor: isDragActive ? '#3B82F6' : undefined,
         transform: isDragActive ? 'scale(1.02)' : undefined,
       }}
     >
       <input {...getInputProps()} />
       <motion.div
         initial={{ opacity: 0, y: 20 }}
         animate={{ opacity: 1, y: 0 }}
         transition={{ duration: 0.5 }}
         style={{ textAlign: 'center' }}
       >
         <ImageIcon sx={{ fontSize: 64, mb: 2, color: '#94A3B8' }} />
         <Typography variant="h6" gutterBottom sx={{ color: '#1E293B' }}>
           {isDragActive ? 'Drop your image here' : 'Drop image here'}
         </Typography>
         <Typography variant="body2" sx={{ color: '#64748B' }}>
           PNG, JPG up to 10MB
         </Typography>
         {file && (
           <Box sx={{ mt: 2, width: '100%', maxWidth: 400, mx: 'auto' }}>
             <Typography variant="body2" sx={{ color: '#3B82F6', fontWeight: 500 }}>
               {file.name}
             </Typography>
             <LinearProgress 
               variant="determinate" 
               value={uploadProgress}
               sx={{ 
                 mt: 1, 
                 borderRadius: 1,
                 backgroundColor: '#E2E8F0',
                 '& .MuiLinearProgress-bar': {
                   backgroundColor: '#3B82F6'
                 }
               }} 
             />
           </Box>
         )}
       </motion.div>
     </Box>

     <Button
       fullWidth
       variant="contained"
       onClick={onProcess}
       disabled={!file || loading}
       startIcon={loading ? <CircularProgress size={20} color="inherit" /> : <UploadFile />}
       sx={styles.processButton}
     >
       {loading ? processingStates[processingStep]?.message || "Processing..." : "Process Image"}
     </Button>

     <AnimatePresence>
       {loading && (
         <motion.div
           initial={{ opacity: 0, scale: 0.9 }}
           animate={{ opacity: 1, scale: 1 }}
           exit={{ opacity: 0, scale: 0.9 }}
           style={{
             position: 'absolute',
             top: '50%',
             left: '50%',
             transform: 'translate(-50%, -50%)',
             backgroundColor: 'rgba(255, 255, 255, 0.97)',
             padding: '2rem',
             borderRadius: '16px',
             boxShadow: '0 10px 30px rgba(0, 0, 0, 0.1)',
             textAlign: 'center',
             minWidth: '300px'
           }}
         >
           {processingStep === processingStates.length ? (
             <motion.div
               initial={{ scale: 0 }}
               animate={{ scale: 1 }}
               transition={{ type: "spring", stiffness: 200, damping: 10 }}
             >
               <CheckCircleOutline sx={{ fontSize: 50, color: '#10B981', mb: 2 }} />
               <Typography variant="h6" gutterBottom sx={{ color: '#1E293B' }}>
                 Detection Complete!
               </Typography>
             </motion.div>
           ) : (
             <>
               <CircularProgress size={50} sx={{ color: '#3B82F6', mb: 2 }} />
               <Typography variant="h6" gutterBottom sx={{ color: '#1E293B' }}>
                 Processing Image
               </Typography>
               <Typography variant="body2" sx={{ color: '#64748B' }}>
                 {processingStates[processingStep]?.message}
               </Typography>
               <LinearProgress 
                 variant="determinate" 
                 value={(processingStep + 1) * (100 / processingStates.length)}
                 sx={{ 
                   mt: 2,
                   borderRadius: 1,
                   backgroundColor: '#E2E8F0',
                   '& .MuiLinearProgress-bar': {
                     backgroundColor: '#3B82F6'
                   }
                 }} 
               />
             </>
           )}
         </motion.div>
       )}
     </AnimatePresence>
   </Box>
 );
}