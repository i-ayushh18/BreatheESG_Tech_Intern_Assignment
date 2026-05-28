import React, { useState } from 'react';
import { Box, Button, TextField, Typography, Paper } from '@mui/material';
import { uploadFile, IngestionResponse } from '../api';

interface FileUploadProps {
  onUploadSuccess: (result: IngestionResponse) => void;
  clientId?: number;
}

const FileUpload: React.FC<FileUploadProps> = ({ onUploadSuccess, clientId }) => {
  const [sourceType, setSourceType] = useState<string>('sap');
  const [file, setFile] = useState<File | null>(null);
  const [uploading, setUploading] = useState<boolean>(false);
  const [error, setError] = useState<string>('');

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files) {
      setFile(e.target.files[0]);
      setError('');
    }
  };

  const acceptedFileTypes = sourceType === 'utility' ? '.csv' : '.json';

  const handleUpload = async () => {
    if (!file) {
      setError('Please select a file');
      return;
    }

    setUploading(true);
    setError('');

    try {
      if (!clientId) {
        setError('Please select a client before uploading.');
        setUploading(false);
        return;
      }
      const result = await uploadFile(sourceType, file, clientId);
      setUploading(false);
      onUploadSuccess(result);
      setFile(null);
    } catch (err: any) {
      setError('Upload failed: ' + (err.response?.data?.error || err.message));
      setUploading(false);
    }
  };

  return (
    <Paper sx={{ p: 3, mb: 3 }}>
      <Typography variant="h6" gutterBottom>
        Upload Data File
      </Typography>
      
      <Box sx={{ mb: 2 }}>
        <TextField
          select
          fullWidth
          label="Source Type"
          value={sourceType}
          onChange={(e) => setSourceType(e.target.value)}
          slotProps={{ select: { native: true } }}
        >
          <option value="sap">SAP OData (Material Documents)</option>
          <option value="utility">Utility (Electricity)</option>
          <option value="travel">SAP Concur Itinerary v4</option>
        </TextField>
      </Box>

      <Box sx={{ mb: 2 }}>
        <input
          type="file"
          accept={acceptedFileTypes}
          onChange={handleFileChange}
        />
      </Box>

      {error && (
        <Typography color="error" sx={{ mb: 2 }}>
          {error}
        </Typography>
      )}

      <Button
        variant="contained"
        onClick={handleUpload}
        disabled={!file || uploading}
        fullWidth
      >
        {uploading ? 'Uploading...' : 'Upload'}
      </Button>
    </Paper>
  );
};

export default FileUpload;
