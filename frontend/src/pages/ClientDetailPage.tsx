import React, { useState, useEffect, useRef } from 'react';
import { useParams } from 'react-router-dom';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ClientRead, RoleRead, RoleUpdate, RoleStatus, ApiError } from '../types';
import RoleEditor from '../components/RoleEditor';

// Helper to format date strings (YYYY-MM-DD) for input type="date"
const formatDateForInput = (dateString: string | null | undefined): string => {
  if (!dateString) return '';
  try {
    return new Date(dateString).toISOString().split('T')[0];
  } catch (e) {
    return ''; // Handle invalid date string
  }
};

const fetchClient = async (clientId: string): Promise<ClientRead> => {
  const response = await fetch(`/api/clients/${clientId}`);
  if (!response.ok) {
    const errorData: ApiError = await response.json().catch(() => ({ message: 'An unknown error occurred' }));
    throw new Error(errorData.message || `Error ${response.status}: ${response.statusText}`);
  }
  return response.json();
};

const fetchRoles = async (clientId: string): Promise<RoleRead[]> => {
  const response = await fetch(`/api/clients/${clientId}/roles`);
  if (!response.ok) {
    const errorData: ApiError = await response.json().catch(() => ({ message: 'An unknown error occurred' }));
    throw new Error(errorData.message || `Error ${response.status}: ${response.statusText}`);
  }
  return response.json();
};

// Generic update function, payload determines what's updated
const updateRoleMutationFn = async ({ roleId, payload }: { roleId: string; payload: RoleUpdate }): Promise<RoleRead> => {
  const response = await fetch(`/api/roles/${roleId}`, {
    method: 'PATCH',
    headers: {
      'Content-Type': 'application/json',
    },
    body: JSON.stringify(payload),
  });
  if (!response.ok) {
    const errorData: ApiError = await response.json().catch(() => ({ message: 'An unknown error occurred' }));
    throw new Error(errorData.message || `Error ${response.status}: ${response.statusText}`);
  }
  return response.json();
};


const ClientDetailPage: React.FC = () => {
  const { clientId } = useParams<{ clientId: string }>();
  const queryClient = useQueryClient();

  // State for editing role details (company, title, dates)
  const [editingRole, setEditingRole] = useState<Partial<RoleRead> & { revision: number } | null>(null);
  // State for editing input_text_compact (curation)
  const [editingCurationForRoleId, setEditingCurationForRoleId] = useState<string | null>(null);

  const [focusedRoleIndex, setFocusedRoleIndex] = useState<number | null>(null);
  const roleRefs = useRef<(HTMLDivElement | null)[]>([]);

  const { data: client, isLoading: isLoadingClient, error: clientError } = useQuery<ClientRead, Error>({
    queryKey: ['client', clientId],
    queryFn: () => fetchClient(clientId!),
    enabled: !!clientId,
  });

  const { data: roles, isLoading: isLoadingRoles, error: rolesError } = useQuery<RoleRead[], Error>({
    queryKey: ['roles', clientId],
    queryFn: () => fetchRoles(clientId!),
    enabled: !!clientId,
  });

  const currentRoleForCuration = roles?.find(r => r.id === editingCurationForRoleId);

  const roleUpdateMutation = useMutation<RoleRead, Error, { roleId: string; payload: RoleUpdate }>({
    mutationFn: updateRoleMutationFn,
    onSuccess: (updatedRole) => {
      queryClient.setQueryData(['roles', clientId], (oldData: RoleRead[] | undefined) =>
        oldData ? oldData.map(r => r.id === updatedRole.id ? updatedRole : r) : []
      );
      // queryClient.invalidateQueries({ queryKey: ['roles', clientId] }); // Consider more targeted invalidation or rely on setQueryData for immediate feedback
      setEditingRole(null);
      setEditingCurationForRoleId(null); // Close RoleEditor on successful save
    },
    // onError: (error) => { /* Handled by isError and error properties on the mutation hook */ }
  });

  useEffect(() => {
    if (roles && roles.length > 0 && editingRole === null && editingCurationForRoleId === null) { // Only adjust focus if not actively editing
      const firstUnverifiedIndex = roles.findIndex(r => r.status === RoleStatus.Parsed || r.status === RoleStatus.Pending);
      const newFocusedIndex = firstUnverifiedIndex !== -1 ? firstUnverifiedIndex : 0;
      if (focusedRoleIndex !== newFocusedIndex) { // Avoid redundant scrolling if focus is already correct
            setFocusedRoleIndex(newFocusedIndex);
            roleRefs.current[newFocusedIndex]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
      }
    }
  }, [roles, editingRole, editingCurationForRoleId, focusedRoleIndex]);

   useEffect(() => {
    if (roles) {
      roleRefs.current = roleRefs.current.slice(0, roles.length);
    }
  }, [roles]);

  const handleEditRoleDetails = (role: RoleRead) => {
    setEditingCurationForRoleId(null); // Ensure curation editor is closed
    setEditingRole({ ...role });
  };

  const handleCancelEditRoleDetails = () => {
    setEditingRole(null);
  };

  const handleRoleDetailsInputChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    if (!editingRole) return;
    const { name, value } = e.target;
    setEditingRole(prev => ({ ...prev!, [name]: value }));
  };

  const handleRoleDetailsDateChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!editingRole) return;
    const { name, value } = e.target;
    setEditingRole(prev => ({ ...prev!, [name]: value ? value : null }));
  };

  const handleSaveRoleDetails = (roleToSave: Partial<RoleRead> & { revision: number }) => {
    if (!roleToSave || !roleToSave.id) return;
    const payload: RoleUpdate = {
      company_name: roleToSave.company_name,
      title: roleToSave.title,
      start_date: roleToSave.start_date || null,
      end_date: roleToSave.end_date || null,
      status: RoleStatus.RolesVerified,
      revision: roleToSave.revision,
    };
    roleUpdateMutation.mutate({ roleId: roleToSave.id, payload });
  };

  // --- Curation Specific Handlers ---
  const handleOpenCurationEditor = (role: RoleRead) => {
    setEditingRole(null); // Ensure role details editor is closed
    setEditingCurationForRoleId(role.id);
  };

  const handleCancelCuration = () => {
    setEditingCurationForRoleId(null);
  };

  const handleSaveCuration = async (updatedData: { input_text_compact: string; revision: number; newStatus: RoleStatus }) => {
    if (!editingCurationForRoleId) return;
    const payload: RoleUpdate = {
      input_text_compact: updatedData.input_text_compact,
      status: updatedData.newStatus,
      revision: updatedData.revision,
    };
    await roleUpdateMutation.mutateAsync({ roleId: editingCurationForRoleId, payload });
    // onSuccess in useMutation handles closing the editor
  };

  // Keyboard navigation
  useEffect(() => {
    const handleKeyPress = (event: KeyboardEvent) => {
      if (event.key === 'Enter' && focusedRoleIndex !== null && roles && roles.length > 0) {
        if (!editingRole && !editingCurationForRoleId) { // Only move if not in any editing mode
          event.preventDefault();
          const nextIndex = (focusedRoleIndex + 1) % roles.length;
          setFocusedRoleIndex(nextIndex);
          roleRefs.current[nextIndex]?.scrollIntoView({ behavior: 'smooth', block: 'center' });
          roleRefs.current[nextIndex]?.focus();
        }
      }
    };
    window.addEventListener('keydown', handleKeyPress);
    return () => window.removeEventListener('keydown', handleKeyPress);
  }, [focusedRoleIndex, roles, editingRole, editingCurationForRoleId]);

  if (isLoadingClient || isLoadingRoles) return <div className="container mx-auto p-4 text-center">Loading client and roles data...</div>;
  if (clientError) return <div className="container mx-auto p-4 text-red-500">Error loading client: {clientError.message}</div>;

  return (
    <div className="container mx-auto p-4">
      {client && (
        <div className="mb-8 p-4 border border-gray-300 rounded-lg shadow">
          <h1 className="text-3xl font-bold mb-2">{client.display_name}</h1>
          {/* ... other client details ... */}
        </div>
      )}

      <h2 className="text-2xl font-semibold mb-4">Role Verification & Curation</h2>

      {rolesError && <div className="bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded mb-6">Error: {rolesError.message}</div>}

      {roles && roles.length === 0 && !rolesError && <p className="text-gray-500">No roles found.</p>}

      {roles && roles.length > 0 && (
        <div className="space-y-6">
          {roles.map((role, index) => (
            <div
              key={role.id}
              ref={el => roleRefs.current[index] = el}
              tabIndex={-1}
              className={`rounded-lg shadow-md transition-all duration-200 ease-in-out
                ${focusedRoleIndex === index && !editingRole && !editingCurationForRoleId ? 'ring-2 ring-blue-500' : 'border border-gray-200'}
                ${editingRole?.id === role.id ? 'bg-blue-50 p-6' : editingCurationForRoleId === role.id ? 'bg-green-50 p-0' : 'bg-white p-6'}`}
            >
              {editingRole?.id === role.id ? (
                // --- Editing Role Details Form ---
                <div className="space-y-4">
                  {/* ... form for company_name, title, dates ... (as before) ... */}
                  <div><label className="block text-sm font-medium text-gray-700">Company Name</label><input type="text" name="company_name" value={editingRole.company_name || ''} onChange={handleRoleDetailsInputChange} className="mt-1 block w-full input-class" /></div>
                  <div><label className="block text-sm font-medium text-gray-700">Title</label><input type="text" name="title" value={editingRole.title || ''} onChange={handleRoleDetailsInputChange} className="mt-1 block w-full input-class" /></div>
                  <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                    <div><label className="block text-sm font-medium text-gray-700">Start Date</label><input type="date" name="start_date" value={formatDateForInput(editingRole.start_date)} onChange={handleRoleDetailsDateChange} className="mt-1 block w-full input-class" /></div>
                    <div><label className="block text-sm font-medium text-gray-700">End Date</label><input type="date" name="end_date" value={formatDateForInput(editingRole.end_date)} onChange={handleRoleDetailsDateChange} className="mt-1 block w-full input-class" /></div>
                  </div>
                  <p className="text-sm text-gray-600">Status: <span className="font-semibold">{editingRole.status}</span> (will be updated to RolesVerified)</p>
                  <p className="text-sm text-gray-600">Revision: {editingRole.revision}</p>
                  <div className="mt-4"><h4 className="text-md font-semibold text-gray-700 mb-1">Raw Output Text (Read-only):</h4><div className="p-3 bg-gray-100 rounded-md max-h-40 overflow-y-auto text-sm whitespace-pre-wrap">{role.output_text}</div></div>
                  <div className="flex justify-end space-x-3 mt-6">
                    <button onClick={handleCancelEditRoleDetails} className="btn-secondary">Cancel</button>
                    <button onClick={() => handleSaveRoleDetails(editingRole)} disabled={roleUpdateMutation.isPending && editingRole?.id === role.id} className="btn-primary">
                      {roleUpdateMutation.isPending && editingRole?.id === role.id ? 'Saving...' : 'Save & Verify Role'}
                    </button>
                  </div>
                </div>
              ) : editingCurationForRoleId === role.id && currentRoleForCuration ? (
                // --- Editing Curation Text ---
                <RoleEditor
                  role={{ id: currentRoleForCuration.id, input_text_compact: currentRoleForCuration.input_text_compact, revision: currentRoleForCuration.revision, status: currentRoleForCuration.status }}
                  onSave={handleSaveCuration}
                  onCancel={handleCancelCuration}
                  isSaving={roleUpdateMutation.isPending && editingCurationForRoleId === role.id}
                />
              ) : (
                // --- Display State for Role ---
                <div className="grid grid-cols-1 md:grid-cols-3 gap-x-6">
                  <div className="md:col-span-2 space-y-3">
                    <h3 className="text-xl font-semibold text-blue-700">{role.company_name}</h3>
                    <p className="text-md text-gray-800">{role.title}</p>
                    <p className="text-sm text-gray-600">{role.start_date ? formatDateForInput(role.start_date) : 'N/A'} - {role.end_date ? formatDateForInput(role.end_date) : 'Present'}</p>
                    <p className={`text-sm font-medium px-2 py-1 inline-block rounded-full ${ role.status === RoleStatus.RolesVerified ? 'bg-green-100 text-green-800' : role.status === RoleStatus.InputCurated ? 'bg-blue-100 text-blue-800' : role.status === RoleStatus.Parsed ? 'bg-yellow-100 text-yellow-800' : 'bg-gray-100 text-gray-800'}`}>Status: {role.status}</p>
                    <p className="text-xs text-gray-500">Revision: {role.revision}</p>
                    <div className="flex space-x-2 mt-4">
                        <button onClick={() => handleEditRoleDetails(role)} className="btn-secondary text-sm">Edit Details</button>
                        <button onClick={() => handleOpenCurationEditor(role)} className="btn-secondary text-sm">Curate Input Text</button>
                    </div>
                  </div>
                  <div className="md:col-span-1 mt-4 md:mt-0">
                    <h4 className="text-sm font-semibold text-gray-700 mb-1">Raw Output Text:</h4>
                    <div className="p-3 bg-gray-50 rounded-md max-h-48 overflow-y-auto text-xs text-gray-600 whitespace-pre-wrap border">{role.output_text}</div>
                    {role.input_text_compact && (
                        <div className="mt-2">
                            <h4 className="text-sm font-semibold text-gray-700 mb-1">Curated Input Text:</h4>
                            <div className="p-3 bg-gray-50 rounded-md max-h-32 overflow-y-auto text-xs text-gray-600 whitespace-pre-wrap border">{role.input_text_compact}</div>
                        </div>
                    )}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
       {roleUpdateMutation.isError && (
        <div className="mt-6 bg-red-100 border border-red-400 text-red-700 px-4 py-3 rounded relative" role="alert">
          <strong className="font-bold">Update Error!</strong>
          <span className="block sm:inline"> {roleUpdateMutation.error?.message || 'Failed to update role.'}</span>
        </div>
      )}
    </div>
  );
};

// Minimalistic CSS classes to be defined in index.css or as Tailwind utility compositions if preferred
// .input-class { @apply mt-1 block w-full px-3 py-2 border border-gray-300 rounded-md shadow-sm focus:outline-none focus:ring-indigo-500 focus:border-indigo-500 sm:text-sm; }
// .btn-primary { @apply px-4 py-2 text-sm font-medium text-white bg-blue-600 hover:bg-blue-700 rounded-md shadow-sm disabled:bg-blue-300; }
// .btn-secondary { @apply px-4 py-2 text-sm font-medium text-gray-700 bg-gray-200 hover:bg-gray-300 rounded-md shadow-sm disabled:opacity-50; }


export default ClientDetailPage;
