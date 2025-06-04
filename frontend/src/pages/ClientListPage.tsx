import React from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { ClientRead, ApiError } from '../types';

const fetchClients = async (): Promise<ClientRead[]> => {
  const response = await fetch('/api/clients');
  if (!response.ok) {
    const errorData: ApiError = await response.json().catch(() => ({ message: 'An unknown error occurred' }));
    throw new Error(errorData.message || `Error ${response.status}: ${response.statusText}`);
  }
  return response.json();
};

const ClientListPage: React.FC = () => {
  const { data: clients, isLoading, error, isError } = useQuery<ClientRead[], Error>({
    queryKey: ['clients'],
    queryFn: fetchClients,
  });

  return (
    <div className="container mx-auto p-4">
      <div className="flex justify-between items-center mb-6">
        <h1 className="text-3xl font-bold">Clients</h1>
        <Link
          to="/client/new" // Or a dedicated add client route, for now a placeholder
          className="bg-blue-500 hover:bg-blue-700 text-white font-bold py-2 px-4 rounded-full shadow-lg transition duration-150 ease-in-out"
        >
          + Add Client
        </Link>
      </div>

      {isLoading && (
        <div className="text-center py-10">
          <p className="text-xl text-gray-500">Loading clients...</p>
          {/* You could add a spinner here */}
        </div>
      )}

      {isError && (
        <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative mb-6" role="alert">
          <strong className="font-bold">Error!</strong>
          <span className="block sm:inline"> {error?.message || 'Failed to fetch clients.'}</span>
        </div>
      )}

      {clients && clients.length === 0 && !isLoading && !isError && (
        <div className="text-center py-10">
          <p className="text-xl text-gray-500">No clients found.</p>
          <p className="mt-2 text-gray-400">Get started by adding a new client.</p>
        </div>
      )}

      {clients && clients.length > 0 && (
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
          {clients.map((client) => (
            <Link
              key={client.id}
              to={`/client/${client.id}`}
              className="block p-6 bg-white border border-gray-200 rounded-lg shadow hover:bg-gray-100 transition-shadow duration-150 ease-in-out"
            >
              <h5 className="mb-2 text-2xl font-bold tracking-tight text-gray-900">{client.display_name}</h5>
              {client.notes && (
                <p className="font-normal text-gray-700 mb-2 truncate">{client.notes}</p>
              )}
              <p className="text-sm text-gray-500">
                Created: {new Date(client.created_at).toLocaleDateString()}
              </p>
            </Link>
          ))}
        </div>
      )}
    </div>
  );
};

export default ClientListPage;
