import React from 'react';
import { Sidebar } from './Sidebar';

export { Sidebar };

/**
 * Navbar component converted to vertical Sidebar for modern LMS layout.
 * Re-exports Sidebar as Navbar for backward compatibility.
 */
export const Navbar: React.FC = () => {
  return <Sidebar />;
};

export default Navbar;
