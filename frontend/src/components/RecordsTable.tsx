import React, { useState, useEffect } from 'react';
import {
  Box,
  Table,
  TableBody,
  TableCell,
  TableContainer,
  TableHead,
  TableRow,
  Paper,
  Button,
  Chip,
  TextField,
  Select,
  MenuItem,
  FormControl,
  InputLabel,
  Checkbox,
  Dialog,
  DialogTitle,
  DialogContent,
  DialogActions,
  Typography,
  Alert,
  Tooltip
} from '@mui/material';
import {
  getRecords,
  getInvalidRawRecords,
  approveRecord,
  flagRecord,
  bulkApprove,
  getAuditLog,
  NormalizedRecord,
  AuditLog,
  RawRecordIssue
} from '../api';

type RecordsTableProps = {
  clientId?: number;
  reloadTrigger?: number;
};

const RecordsTable: React.FC<RecordsTableProps> = ({ clientId, reloadTrigger }) => {
  const [records, setRecords] = useState<NormalizedRecord[]>([]);
  const [invalidRows, setInvalidRows] = useState<RawRecordIssue[]>([]);
  const [loading, setLoading] = useState<boolean>(false);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [filters, setFilters] = useState({
    status: '',
    scope: '',
    activity_type: ''
  });
  const [flagDialog, setFlagDialog] = useState({ open: false, recordId: 0, reason: '' });
  const [auditDialog, setAuditDialog] = useState<{ open: boolean; logs: AuditLog[] }>({ open: false, logs: [] });

  const fetchRecords = async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = { ...filters } as Record<string, string>;
      if (clientId) params.client_id = String(clientId);

      const [data, invalidData] = await Promise.all([
        getRecords(params),
        getInvalidRawRecords(clientId ? { client_id: String(clientId) } : {})
      ]);
      setRecords(data);
      setInvalidRows(invalidData);
    } catch (err) {
      console.error('Failed to fetch records:', err);
    }
    setLoading(false);
  };

  useEffect(() => {
    fetchRecords();
  }, [filters, clientId, reloadTrigger]);

  const handleSelectAll = (event: React.ChangeEvent<HTMLInputElement>) => {
    if (event.target.checked) {
      setSelectedIds(records.map(r => r.id));
    } else {
      setSelectedIds([]);
    }
  };

  const handleSelectOne = (id: number) => {
    setSelectedIds(prev => 
      prev.includes(id) ? prev.filter(x => x !== id) : [...prev, id]
    );
  };

  const handleApprove = async (id: number) => {
    try {
      await approveRecord(id);
      fetchRecords();
    } catch (err) {
      console.error('Failed to approve:', err);
    }
  };

  const handleFlag = async () => {
    try {
      await flagRecord(flagDialog.recordId, flagDialog.reason);
      setFlagDialog({ open: false, recordId: 0, reason: '' });
      fetchRecords();
    } catch (err) {
      console.error('Failed to flag:', err);
    }
  };

  const handleBulkApprove = async () => {
    try {
      await bulkApprove(selectedIds);
      setSelectedIds([]);
      fetchRecords();
    } catch (err) {
      console.error('Failed to bulk approve:', err);
    }
  };

  const handleViewAudit = async (id: number) => {
    try {
      const logs = await getAuditLog(id);
      setAuditDialog({ open: true, logs });
    } catch (err) {
      console.error('Failed to fetch audit log:', err);
    }
  };

  const getStatusColor = (status: string): 'warning' | 'success' | 'error' | 'default' => {
    const colors: Record<string, 'warning' | 'success' | 'error' | 'default'> = {
      pending: 'warning',
      approved: 'success',
      flagged: 'error',
      locked: 'default'
    };
    return colors[status] || 'default';
  };

  const getFlagColor = (severity?: string): 'warning' | 'error' | 'default' => {
    if (severity === 'error') {
      return 'error';
    }
    if (severity === 'warning') {
      return 'warning';
    }
    return 'default';
  };

  const summarizeRawData = (rawData: Record<string, unknown>): string => {
    return Object.entries(rawData)
      .slice(0, 4)
      .map(([key, value]) => `${key}: ${String(value)}`)
      .join(', ');
  };

  return (
    <Paper sx={{ p: 3 }}>
      <Box sx={{ display: 'flex', gap: 2, mb: 3, flexWrap: 'wrap' }}>
        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel>Status</InputLabel>
          <Select
            value={filters.status}
            label="Status"
            onChange={(e) => setFilters({ ...filters, status: e.target.value })}
          >
            <MenuItem value="">All</MenuItem>
            <MenuItem value="pending">Pending</MenuItem>
            <MenuItem value="approved">Approved</MenuItem>
            <MenuItem value="flagged">Flagged</MenuItem>
            <MenuItem value="locked">Locked</MenuItem>
          </Select>
        </FormControl>

        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel>Scope</InputLabel>
          <Select
            value={filters.scope}
            label="Scope"
            onChange={(e) => setFilters({ ...filters, scope: e.target.value })}
          >
            <MenuItem value="">All</MenuItem>
            <MenuItem value="1">Scope 1</MenuItem>
            <MenuItem value="2">Scope 2</MenuItem>
            <MenuItem value="3">Scope 3</MenuItem>
          </Select>
        </FormControl>

        <FormControl size="small" sx={{ minWidth: 120 }}>
          <InputLabel>Activity Type</InputLabel>
          <Select
            value={filters.activity_type}
            label="Activity Type"
            onChange={(e) => setFilters({ ...filters, activity_type: e.target.value })}
          >
            <MenuItem value="">All</MenuItem>
            <MenuItem value="fuel">Fuel</MenuItem>
            <MenuItem value="electricity">Electricity</MenuItem>
            <MenuItem value="flight">Flight</MenuItem>
            <MenuItem value="hotel">Hotel</MenuItem>
            <MenuItem value="ground">Ground</MenuItem>
          </Select>
        </FormControl>

        {selectedIds.length > 0 && (
          <Button
            variant="contained"
            color="success"
            onClick={handleBulkApprove}
          >
            Approve Selected ({selectedIds.length})
          </Button>
        )}
      </Box>

      {invalidRows.length > 0 && (
        <Box sx={{ mb: 3 }}>
          <Alert severity="warning" sx={{ mb: 2 }}>
            {invalidRows.length} uploaded row{invalidRows.length === 1 ? '' : 's'} did not create normalized records.
          </Alert>
          <TableContainer sx={{ maxHeight: 260 }}>
            <Table size="small" stickyHeader>
              <TableHead>
                <TableRow>
                  <TableCell>Source</TableCell>
                  <TableCell>File</TableCell>
                  <TableCell>Row</TableCell>
                  <TableCell>Issue</TableCell>
                  <TableCell>Raw data</TableCell>
                </TableRow>
              </TableHead>
              <TableBody>
                {invalidRows.map((row) => (
                  <TableRow key={row.id}>
                    <TableCell>{row.ingestion_source_type}</TableCell>
                    <TableCell>{row.ingestion_filename}</TableCell>
                    <TableCell>{row.row_number}</TableCell>
                    <TableCell>{row.validation_error}</TableCell>
                    <TableCell>{summarizeRawData(row.raw_data)}</TableCell>
                  </TableRow>
                ))}
              </TableBody>
            </Table>
          </TableContainer>
        </Box>
      )}

      <TableContainer>
        <Table>
          <TableHead>
            <TableRow>
              <TableCell padding="checkbox">
                <Checkbox
                  checked={selectedIds.length === records.length && records.length > 0}
                  onChange={handleSelectAll}
                />
              </TableCell>
              <TableCell>Facility</TableCell>
              <TableCell>Activity Type</TableCell>
              <TableCell>Scope</TableCell>
              <TableCell>Value</TableCell>
              <TableCell>Unit</TableCell>
              <TableCell>CO2e (kg)</TableCell>
              <TableCell>Review Flags</TableCell>
              <TableCell>Status</TableCell>
              <TableCell>Actions</TableCell>
            </TableRow>
          </TableHead>
          <TableBody>
            {records.map((record) => (
              <TableRow key={record.id}>
                <TableCell padding="checkbox">
                  <Checkbox
                    checked={selectedIds.includes(record.id)}
                    onChange={() => handleSelectOne(record.id)}
                  />
                </TableCell>
                <TableCell>{record.facility}</TableCell>
                <TableCell>{record.activity_type}</TableCell>
                <TableCell>Scope {record.scope}</TableCell>
                <TableCell>{record.activity_value.toFixed(2)}</TableCell>
                <TableCell>{record.activity_unit}</TableCell>
                <TableCell>{record.co2e_kg.toFixed(2)}</TableCell>
                <TableCell>
                  {record.flag_count && record.flag_count > 0 ? (
                    <Tooltip title={record.quality_flags?.map(flag => flag.description).join(' | ') || ''}>
                      <Chip
                        label={`${record.flag_count} ${record.highest_severity || 'flag'}`}
                        color={getFlagColor(record.highest_severity)}
                        size="small"
                      />
                    </Tooltip>
                  ) : (
                    <Chip label="None" size="small" variant="outlined" />
                  )}
                </TableCell>
                <TableCell>
                  <Chip label={record.status} color={getStatusColor(record.status)} size="small" />
                </TableCell>
                <TableCell>
                  {record.status === 'pending' || record.status === 'flagged' ? (
                    <>
                      <Button
                        size="small"
                        onClick={() => handleApprove(record.id)}
                        sx={{ mr: 1 }}
                      >
                        Approve
                      </Button>
                      <Button
                        size="small"
                        color="error"
                        onClick={() => setFlagDialog({ open: true, recordId: record.id, reason: '' })}
                      >
                        Flag
                      </Button>
                      <Button
                        size="small"
                        onClick={() => handleViewAudit(record.id)}
                      >
                        Audit
                      </Button>
                    </>
                  ) : (
                    <Button
                      size="small"
                      onClick={() => handleViewAudit(record.id)}
                    >
                      Audit
                    </Button>
                  )}
                </TableCell>
              </TableRow>
            ))}
            {records.length === 0 && !loading && (
              <TableRow>
                <TableCell colSpan={10}>
                  <Typography color="text.secondary">No records match the current filters.</Typography>
                </TableCell>
              </TableRow>
            )}
          </TableBody>
        </Table>
      </TableContainer>

      <Dialog open={flagDialog.open} onClose={() => setFlagDialog({ open: false, recordId: 0, reason: '' })}>
        <DialogTitle>Flag Record</DialogTitle>
        <DialogContent>
          <TextField
            autoFocus
            margin="dense"
            label="Reason"
            fullWidth
            multiline
            rows={4}
            value={flagDialog.reason}
            onChange={(e) => setFlagDialog({ ...flagDialog, reason: e.target.value })}
          />
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setFlagDialog({ open: false, recordId: 0, reason: '' })}>
            Cancel
          </Button>
          <Button onClick={handleFlag} variant="contained">
            Flag
          </Button>
        </DialogActions>
      </Dialog>

      <Dialog open={auditDialog.open} onClose={() => setAuditDialog({ open: false, logs: [] })} maxWidth="md" fullWidth>
        <DialogTitle>Audit Log</DialogTitle>
        <DialogContent>
          {auditDialog.logs.length === 0 ? (
            <Typography>No audit logs available</Typography>
          ) : (
            auditDialog.logs.map((log) => (
              <Box key={log.id} sx={{ mb: 2, p: 2, bgcolor: 'grey.100', borderRadius: 1 }}>
                <Typography variant="body2" color="text.secondary">
                  {new Date(log.changed_at).toLocaleString()}
                </Typography>
                <Typography variant="body1">
                  <strong>{log.field_name}:</strong> {log.old_value} → {log.new_value}
                </Typography>
                <Typography variant="body2">{log.reason}</Typography>
              </Box>
            ))
          )}
        </DialogContent>
        <DialogActions>
          <Button onClick={() => setAuditDialog({ open: false, logs: [] })}>
            Close
          </Button>
        </DialogActions>
      </Dialog>
    </Paper>
  );
};

export default RecordsTable;
