import { test, expect, Page } from '@playwright/test';
import { ClientRead, RoleRead, RoleStatus } from '../src/types'; // Adjust path as needed

const BASE_URL = 'http://localhost:3000'; // Assuming default Vite port, will be overridden by playwright.config.ts

// --- Mock Data ---
const MOCK_CLIENT_ALPHA_ID = 'uuid-client-alpha';
const MOCK_CLIENT_BETA_ID = 'uuid-client-beta';

const MOCK_CLIENTS_LIST: ClientRead[] = [
  { id: MOCK_CLIENT_ALPHA_ID, display_name: 'Client Alpha', notes: 'Notes for Alpha', created_at: '2023-01-01T10:00:00Z' },
  { id: MOCK_CLIENT_BETA_ID, display_name: 'Client Beta', notes: null, created_at: '2023-01-02T11:00:00Z' },
];

const MOCK_ROLE_PARSED_ID = 'uuid-role-parsed';
const MOCK_ROLE_VERIFIED_ID = 'uuid-role-verified';

const MOCK_ROLES_FOR_ALPHA: RoleRead[] = [
  {
    id: MOCK_ROLE_PARSED_ID,
    client_id: MOCK_CLIENT_ALPHA_ID,
    company_name: 'Old Company',
    title: 'Old Title',
    start_date: '2022-01-01',
    end_date: '2022-12-31',
    output_text: 'Some output text for Old Company.',
    status: RoleStatus.Parsed,
    revision: 1,
    input_text_compact: 'Initial compact text for Old Company',
    created_at: '2023-01-01T10:00:00Z',
    updated_at: '2023-01-01T10:00:00Z',
  },
  {
    id: MOCK_ROLE_VERIFIED_ID,
    client_id: MOCK_CLIENT_ALPHA_ID,
    company_name: 'Verified Solutions',
    title: 'Verified Engineer',
    start_date: '2021-06-01',
    end_date: null,
    output_text: 'Output for Verified Solutions.',
    status: RoleStatus.RolesVerified, // Suitable for HITL 2 (curation)
    revision: 2,
    input_text_compact: 'Initial compact text for Verified Solutions',
    created_at: '2023-01-01T11:00:00Z',
    updated_at: '2023-01-01T12:00:00Z',
  },
];

// --- Test Suite ---
test.describe('Happy Path E2E Tests', () => {

  test.beforeEach(async ({ page }) => {
    // Common setup:
    // Mock generic client list for any navigation to `/`
    await page.route(`/api/clients`, async route => {
      await route.fulfill({ json: MOCK_CLIENTS_LIST });
    });

    // Mock specific client details (can be overridden in specific tests if needed)
    await page.route(`/api/clients/${MOCK_CLIENT_ALPHA_ID}`, async route => {
      const client = MOCK_CLIENTS_LIST.find(c => c.id === MOCK_CLIENT_ALPHA_ID);
      if (client) {
        await route.fulfill({ json: client });
      } else {
        await route.fulfill({ status: 404, json: { message: 'Client not found' } });
      }
    });

    // Mock roles for Client Alpha (can be overridden)
    await page.route(`/api/clients/${MOCK_CLIENT_ALPHA_ID}/roles`, async route => {
      await route.fulfill({ json: MOCK_ROLES_FOR_ALPHA });
    });
  });

  test('Test 1: Client List and Navigation', async ({ page }) => {
    await page.goto('/');

    // Assert title or heading
    await expect(page.getByRole('heading', { name: 'Clients', level: 1 })).toBeVisible();

    // Assert client names are visible
    await expect(page.getByText('Client Alpha')).toBeVisible();
    await expect(page.getByText('Client Beta')).toBeVisible();

    // Action: Click on the first client
    // Assuming the link is directly on the text or a card containing it
    await page.getByText('Client Alpha').click();

    // Assert URL changes
    await expect(page).toHaveURL(`/client/${MOCK_CLIENT_ALPHA_ID}`);

    // Assert client detail page indication
    // This could be the client's name in a heading or a specific title
    await expect(page.getByRole('heading', { name: 'Client Alpha', level: 1 })).toBeVisible();
    // Or more specific if there's a title like "Client Details"
    // await expect(page.getByRole('heading', { name: /Client.*Details/i })).toBeVisible();
  });


  test('Test 2: Role Verification and Basic Editing (HITL 1)', async ({ page }) => {
    await page.goto(`/client/${MOCK_CLIENT_ALPHA_ID}`);

    // Assert initial role information is visible
    await expect(page.getByText('Old Company')).toBeVisible();
    await expect(page.getByText('Old Title')).toBeVisible();
    await expect(page.getByText('Status: Parsed')).toBeVisible();

    // Action: Click an "Edit" button for the first role
    // Assuming the button is specific to the role card for "Old Company"
    // We use a more robust locator strategy: find the role container, then the button within it.
    const roleContainer = page.locator('.space-y-6 > div', { hasText: 'Old Company' }).first();
    await roleContainer.getByRole('button', { name: 'Edit Details' }).click();

    // Assert editing UI is visible
    await expect(roleContainer.getByLabel('Company Name')).toBeVisible();

    // Action: Fill in a new company name
    const newCompanyName = 'New Company Inc.';
    await roleContainer.getByLabel('Company Name').fill(newCompanyName);

    // Mock API for PATCH /api/roles/role-uuid-A
    let patchPayload: any = null;
    await page.route(`/api/roles/${MOCK_ROLE_PARSED_ID}`, async route => {
      if (route.request().method() === 'PATCH') {
        patchPayload = await route.request().postDataJSON();
        const updatedRole: RoleRead = {
          ...MOCK_ROLES_FOR_ALPHA.find(r => r.id === MOCK_ROLE_PARSED_ID)!,
          company_name: newCompanyName,
          status: RoleStatus.RolesVerified,
          revision: patchPayload.revision + 1, // Assuming backend increments revision
        };
        await route.fulfill({ json: updatedRole });
      } else {
        await route.continue(); // Continue for other methods if any
      }
    });

    // Action: Click the "Save & Verify Role" button
    await roleContainer.getByRole('button', { name: 'Save & Verify Role' }).click();

    // Assert the role's displayed company name updates
    await expect(roleContainer.getByText(newCompanyName)).toBeVisible();
    // Assert status updates (text might be part of a larger string)
    await expect(roleContainer.getByText('Status: RolesVerified')).toBeVisible();

    // Optional: Assert the PATCH payload was as expected
    expect(patchPayload).toBeTruthy();
    expect(patchPayload.company_name).toBe(newCompanyName);
    expect(patchPayload.status).toBe(RoleStatus.RolesVerified);
    expect(patchPayload.revision).toBe(1); // Original revision sent
  });


  test('Test 3: Role Editor Interaction (HITL 2 - input_text_compact)', async ({ page }) => {
    // Ensure we are on the client detail page where the target role exists.
    // The target role for curation is MOCK_ROLE_VERIFIED_ID ('Verified Solutions')
    // which already has status RolesVerified and revision 2.
    await page.goto(`/client/${MOCK_CLIENT_ALPHA_ID}`);

    const roleToCurateContainer = page.locator('.space-y-6 > div', { hasText: 'Verified Solutions' }).first();

    // Assert initial state of the role meant for curation
    await expect(roleToCurateContainer.getByText('Verified Solutions')).toBeVisible();
    await expect(roleToCurateContainer.getByText('Status: RolesVerified')).toBeVisible(); // Initial status

    // Action: Click the "Curate Input Text" button for this role
    await roleToCurateContainer.getByRole('button', { name: 'Curate Input Text' }).click();

    // Assert: The RoleEditor component becomes visible (e.g., a textarea)
    // The RoleEditor has a specific heading.
    await expect(roleToCurateContainer.getByRole('heading', { name: 'Curate Input Text (HITL 2)'})).toBeVisible();
    const textarea = roleToCurateContainer.getByPlaceholder('Enter or edit the compact input text for this role...');
    await expect(textarea).toBeVisible();
    await expect(textarea).toBeEditable();

    // Action: Type new curated input text
    const newCuratedText = 'This is new curated input text.';
    await textarea.fill(newCuratedText);

    // Assert: The token counter updates.
    // The fallback estimator counts words and punctuation. "This is new curated input text." = 7 words + 1 period = 8 tokens.
    await expect(roleToCurateContainer.getByText(/Token Count: 8 \/ 8096/)).toBeVisible();

    // Mock API for PATCH /api/roles/MOCK_ROLE_VERIFIED_ID
    let curatePatchPayload: any = null;
    await page.route(`/api/roles/${MOCK_ROLE_VERIFIED_ID}`, async route => {
      if (route.request().method() === 'PATCH') {
        curatePatchPayload = await route.request().postDataJSON();
        const updatedRole: RoleRead = {
          ...MOCK_ROLES_FOR_ALPHA.find(r => r.id === MOCK_ROLE_VERIFIED_ID)!,
          input_text_compact: newCuratedText,
          status: RoleStatus.InputCurated,
          revision: curatePatchPayload.revision + 1,
        };
        await route.fulfill({ json: updatedRole });
      } else {
        await route.continue();
      }
    });

    // Action: Click the "Save Curation" button
    await roleToCurateContainer.getByRole('button', { name: 'Save Curation' }).click();

    // Assert: The input_text_compact (if displayed on the main role card) updates,
    // and the role's status changes to "InputCurated".
    // The RoleEditor should disappear.
    await expect(roleToCurateContainer.getByRole('heading', { name: 'Curate Input Text (HITL 2)'})).not.toBeVisible();

    // Assert updated status on the card
    await expect(roleToCurateContainer.getByText('Status: InputCurated')).toBeVisible();
    // Assert updated text is shown (if UI displays it - ClientDetailPage was updated to show it)
    await expect(roleToCurateContainer.getByText(newCuratedText)).toBeVisible();


    // Optional: Assert the PATCH payload was as expected
    expect(curatePatchPayload).toBeTruthy();
    expect(curatePatchPayload.input_text_compact).toBe(newCuratedText);
    expect(curatePatchPayload.status).toBe(RoleStatus.InputCurated);
    expect(curatePatchPayload.revision).toBe(2); // Original revision for this role
  });

});
