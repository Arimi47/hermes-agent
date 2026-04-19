/** @type {import('next').NextConfig} */
const nextConfig = {
  // neo4j-driver uses a few Node built-ins that webpack warns about;
  // serverExternalPackages keeps it out of the server bundle.
  serverExternalPackages: ['neo4j-driver'],
};

module.exports = nextConfig;
