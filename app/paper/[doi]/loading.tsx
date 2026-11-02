export default function PaperLoading() {
  return (
    <div className="max-w-4xl mx-auto px-4 sm:px-6 lg:px-8 py-10 animate-pulse">
      {/* Back button skeleton */}
      <div className="h-5 w-32 bg-gray-200 dark:bg-gray-800 rounded mb-8" />

      {/* Main card skeleton */}
      <div className="bg-white dark:bg-gray-900 rounded-xl shadow-sm border border-gray-200 dark:border-gray-800 p-8">
        {/* Badges */}
        <div className="flex gap-2 mb-6">
          <div className="h-6 w-24 bg-gray-200 dark:bg-gray-800 rounded-full" />
          <div className="h-6 w-28 bg-gray-100 dark:bg-gray-800 rounded-full" />
        </div>

        {/* Title */}
        <div className="space-y-3 mb-6">
          <div className="h-8 sm:h-10 w-full bg-gray-200 dark:bg-gray-700 rounded" />
          <div className="h-8 sm:h-10 w-4/5 bg-gray-200 dark:bg-gray-700 rounded" />
        </div>

        {/* Authors */}
        <div className="space-y-2 mb-8">
          <div className="h-4 w-20 bg-gray-200 dark:bg-gray-700 rounded" />
          <div className="h-5 w-2/3 bg-gray-100 dark:bg-gray-800 rounded" />
        </div>

        {/* Buttons (Cite, DOI) */}
        <div className="flex gap-3 mb-8">
          <div className="h-9 w-20 bg-gray-200 dark:bg-gray-800 rounded-md" />
          <div className="h-9 w-28 bg-gray-200 dark:bg-gray-800 rounded-md" />
        </div>

        {/* Metadata grid */}
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 p-4 bg-gray-50 dark:bg-gray-800/50 rounded-lg mb-8">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="space-y-1">
              <div className="h-3 w-16 bg-gray-200 dark:bg-gray-700 rounded" />
              <div className="h-4 w-24 bg-gray-100 dark:bg-gray-800 rounded" />
            </div>
          ))}
        </div>

        {/* Abstract */}
        <div className="space-y-3">
          <div className="h-5 w-24 bg-gray-200 dark:bg-gray-700 rounded" />
          <div className="h-4 w-full bg-gray-100 dark:bg-gray-800 rounded" />
          <div className="h-4 w-full bg-gray-100 dark:bg-gray-800 rounded" />
          <div className="h-4 w-5/6 bg-gray-100 dark:bg-gray-800 rounded" />
          <div className="h-4 w-3/4 bg-gray-100 dark:bg-gray-800 rounded" />
        </div>
      </div>
    </div>
  );
}
