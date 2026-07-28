import React, { useState, useEffect } from 'react';
import { Link, useParams, useNavigate } from 'react-router-dom';
import API from '../api';

export default function Openings() {
  const { company_id } = useParams();
  const navigate = useNavigate();
  const [openings, setOpenings] = useState([]);
  const [title, setTitle] = useState('');

  useEffect(() => {
    fetchOpenings();
  }, [company_id]);

  async function fetchOpenings() {
    try {
      const { data } = await API.get(`/api/companies/${company_id}/openings`);
      setOpenings(data);
    } catch (e) {
      console.error(e);
    }
  }

  async function handleAdd(e) {
    e.preventDefault();
    if (!title) return;
    try {
      await API.post(`/api/companies/${company_id}/openings`, { title });
      setTitle('');
      fetchOpenings();
    } catch (e) {
      console.error(e);
    }
  }

  return (
    <div className="page gap-20">
      <div className="flex-row gap-12" style={{marginBottom: 20}}>
        <button className="btn-ghost btn-sm" onClick={() => navigate('/companies')}>← Back</button>
        <h1 className="page-title" style={{margin:0}}>Job Openings</h1>
      </div>
      
      <div className="card" style={{padding: '24px'}}>
        <div style={{fontWeight: 600, marginBottom: 12}}>Add New Opening</div>
        <form onSubmit={handleAdd} className="flex-row">
          <input 
            value={title} 
            onChange={e => setTitle(e.target.value)} 
            placeholder="E.g., Senior Frontend Engineer" 
          />
          <button className="btn-primary" type="submit">Create</button>
        </form>
      </div>

      <div className="gap-12">
        {openings.length === 0 && <div className="text-secondary text-sm">No openings found.</div>}
        {openings.map(o => (
          <Link to={`/openings/${o.id}`} key={o.id} style={{textDecoration:'none', color:'inherit'}}>
            <div className="card" style={{padding: '20px'}}>
              <div style={{fontWeight: 600, fontSize: 16, color: 'var(--accent)'}}>{o.title}</div>
              <div className="text-secondary text-sm mt-4">
                Created {new Date(o.created_at).toLocaleDateString()}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
