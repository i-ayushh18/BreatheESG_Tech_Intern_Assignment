import React, { useState, useEffect } from 'react';
import { Container, Typography, FormControl, InputLabel, Select, MenuItem } from '@mui/material';
import FileUpload from './components/FileUpload';
import RecordsTable from './components/RecordsTable';
import { IngestionResponse, getClients } from './api';

function App() {
  const [uploadSuccess, setUploadSuccess] = useState<boolean>(false);
  const [uploadCounter, setUploadCounter] = useState<number>(0);
  const [clients, setClients] = useState<any[]>([]);
  const [selectedClientId, setSelectedClientId] = useState<number | undefined>(undefined);

  useEffect(() => {
    (async () => {
      try {
        const c = await getClients();
        setClients(c || []);
        if (c && c.length > 0) setSelectedClientId(c[0].id);
      } catch (err) {
        console.error('Failed to load clients', err);
      }
    })();
  }, []);

  const handleUploadSuccess = (result: IngestionResponse) => {
    setUploadSuccess(true);
    setUploadCounter((c) => c + 1);
    setTimeout(() => setUploadSuccess(false), 3000);
  };

  return (
    <Container maxWidth="xl" sx={{ py: 4 }}>
      <Typography variant="h4" component="h1" gutterBottom>
        Breathe ESG Carbon Accounting Platform
      </Typography>
      
      <FormControl sx={{ minWidth: 240, mb: 2 }} size="small">
        <InputLabel>Client</InputLabel>
        <Select
          value={selectedClientId ?? ''}
          label="Client"
          onChange={(e) => setSelectedClientId(Number(e.target.value) || undefined)}
        >
          {Array.isArray(clients) ? clients.map((c) => (
              <MenuItem key={c.id} value={c.id}>{c.name}</MenuItem>
            )) : null}
        </Select>
      </FormControl>

      <FileUpload onUploadSuccess={handleUploadSuccess} clientId={selectedClientId} />

      <RecordsTable clientId={selectedClientId} reloadTrigger={uploadCounter} />
    </Container>
  );
}

export default App;
