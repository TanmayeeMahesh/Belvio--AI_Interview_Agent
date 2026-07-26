import React, { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import API from '../api';

export default function Companies() {
  const [companies, setCompanies] = useState([]);
  const [name, setName] = useState('');

  useEffect(() => {
    fetchCompanies();
  }, []);

  async function fetchCompanies() {
    try {
      const { data } = await API.get('/api/companies');
      setCompanies(data);
    } catch (e) {
      console.error(e);
    }
  }

  async function handleAdd(e) {
    e.preventDefault();
    if (!name) return;
    try {
      await API.post('/api/companies', { name });
      setName('');
      fetchCompanies();
    } catch (e) {
      console.error(e);
    }
  }

  return (
    <div className="page gap-20">
      <div className="flex-between">
        <div>
          <h1 className="page-title" style={{margin:0}}>Companies</h1>
          <p className="text-secondary" style={{ marginTop: 4, marginBottom: 0, fontSize: 14 }}>Manage client organizations onboarded to the platform.</p>
        </div>
      </div>
      
      <div className="card" style={{padding: '24px'}}>
        <div style={{fontWeight: 600, marginBottom: 12}}>Add New Company</div>
        <form onSubmit={handleAdd} className="flex-row">
          <input 
            value={name} 
            onChange={e => setName(e.target.value)} 
            placeholder="E.g., Acme Corp" 
          />
          <button className="btn-primary" type="submit">Create</button>
        </form>
      </div>

      <div className="gap-12">
        {companies.length === 0 && <div className="text-secondary text-sm">No companies yet.</div>}
        {companies.map(c => (
          <Link to={`/companies/${c.id}`} key={c.id} style={{textDecoration:'none', color:'inherit'}}>
            <div className="card" style={{padding: '20px'}}>
              <div style={{fontWeight: 600, fontSize: 16, color: 'var(--accent)'}}>{c.name}</div>
              <div className="text-secondary text-sm mt-4">
                Added {new Date(c.created_at).toLocaleDateString()}
              </div>
            </div>
          </Link>
        ))}
      </div>
    </div>
  );
}
