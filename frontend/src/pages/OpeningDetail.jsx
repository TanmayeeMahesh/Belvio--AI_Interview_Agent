import React, { useState, useEffect } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import API from '../api';
import Sessions from './Sessions';

export default function OpeningDetail({ token, onViewReport }) {
  const { opening_id } = useParams();
  const navigate = useNavigate();
  const [opening, setOpening] = useState(null);
  const [jdText, setJdText] = useState('');
  const [metadataStr, setMetadataStr] = useState('');
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    fetchOpening();
  }, [opening_id]);

  async function fetchOpening() {
    try {
      const { data } = await API.get(`/api/openings/${opening_id}`);
      setOpening(data);
      setJdText(data.jd_text || '');
      setMetadataStr(JSON.stringify(data.metadata || {}, null, 2));
    } catch (e) {
      console.error(e);
    }
  }

  async function handleSave() {
    setSaving(true);
    try {
      let meta = {};
      try {
        meta = JSON.parse(metadataStr);
      } catch (err) {
        alert("Metadata must be valid JSON");
        setSaving(false);
        return;
      }
      await API.put(`/api/openings/${opening_id}`, { jd_text: jdText, metadata: meta });
      alert("Saved successfully!");
      fetchOpening();
    } catch (e) {
      console.error(e);
      alert("Failed to save");
    }
    setSaving(false);
  }

  if (!opening) return <div className="page text-secondary">Loading...</div>;

  return (
    <div className="page gap-20">
      <div className="flex-row gap-12" style={{marginBottom: 20}}>
        <button className="btn-ghost btn-sm" onClick={() => navigate(-1)}>← Back</button>
        <h1 className="page-title" style={{margin:0}}>{opening.title}</h1>
      </div>
      
      <div className="grid-2">
        <div className="card gap-12" style={{padding: '24px'}}>
          <div style={{fontWeight: 600}}>Job Description (JD)</div>
          <textarea 
            rows={12} 
            value={jdText} 
            onChange={e => setJdText(e.target.value)}
            placeholder="Paste Job Description here..."
          />
        </div>
        
        <div className="card gap-12" style={{padding: '24px'}}>
          <div style={{fontWeight: 600}}>Additional Metadata (JSON)</div>
          <textarea 
            rows={12} 
            value={metadataStr} 
            onChange={e => setMetadataStr(e.target.value)}
            placeholder='{"department": "Engineering", "level": "Senior"}'
            style={{fontFamily: 'monospace'}}
          />
        </div>
      </div>
      
      <div className="flex-row" style={{justifyContent: 'flex-end'}}>
        <button className="btn-primary" onClick={handleSave} disabled={saving}>
          {saving ? 'Saving...' : 'Save Details'}
        </button>
      </div>

      <hr className="divider" />
      <div style={{fontWeight: 600, fontSize: 18, marginTop: 10, marginBottom: 10}}>Candidates & Sessions</div>
      <div style={{margin: '-28px -24px'}}> 
        <Sessions token={token} onViewReport={onViewReport} openingId={opening_id} hideHeader={true} />
      </div>
    </div>
  );
}
