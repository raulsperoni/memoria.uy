// Debug helper - paste this in browser console on any page
// To check current API URL:
chrome.storage.sync.get(['apiUrl'], function(result) {
  console.log('Current API URL:', result.apiUrl);
});

// To manually set API URL:
// chrome.storage.sync.set({ apiUrl: 'https://memoria.uy' }, function() {
//   console.log('API URL updated to https://memoria.uy');
// });
