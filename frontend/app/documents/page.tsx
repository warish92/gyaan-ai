"use client";

import React, { useState, useEffect, useCallback, useRef } from "react";
import Link from "next/link";
import {
  FileText,
  Upload,
  Search,
  Trash2,
  RefreshCw,
  AlertCircle,
  CheckCircle2,
  Clock,
  BookOpen,
  GraduationCap,
  Layers,
  Sparkles,
  ShieldCheck,
  X,
  FileCheck,
  ArrowRight,
  Info,
} from "lucide-react";
import { PageHeader } from "../../components/ui/PageHeader";
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from "../../components/ui/Card";
import { Button } from "../../components/ui/Button";
import { Badge } from "../../components/ui/Badge";
import { EmptyState } from "../../components/ui/EmptyState";
import { Spinner } from "../../components/ui/LoadingIndicator";
import { useAuth } from "../../components/auth/AuthContext";
import { apiClient, ApiError } from "../../lib/api";
import {
  DocumentMetadataResponse,
  DocumentSearchResponse,
  DocumentSearchResultItem,
} from "../../types";

const MAX_FILE_SIZE_BYTES = 10 * 1024 * 1024; // 10 MB

function formatBytes(bytes: number, decimals = 1): string {
  if (bytes === 0) return "0 Bytes";
  const k = 1024;
  const dm = decimals < 0 ? 0 : decimals;
  const sizes = ["Bytes", "KB", "MB", "GB"];
  const i = Math.floor(Math.log(bytes) / Math.log(k));
  return parseFloat((bytes / Math.pow(k, i)).toFixed(dm)) + " " + sizes[i];
}

export default function DocumentLibraryPage() {
  const { student, isAuthenticated, token, isLoading: authLoading } = useAuth();

  // Documents list state
  const [documents, setDocuments] = useState<DocumentMetadataResponse[]>([]);
  const [isLoadingDocs, setIsLoadingDocs] = useState<boolean>(true);
  const [docsError, setDocsError] = useState<string | null>(null);

  // Upload state
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState<boolean>(false);
  const [isUploading, setIsUploading] = useState<boolean>(false);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadSuccess, setUploadSuccess] = useState<string | null>(null);

  // Search state
  const [searchQuery, setSearchQuery] = useState<string>("");
  const [isSearching, setIsSearching] = useState<boolean>(false);
  const [searchResults, setSearchResults] = useState<DocumentSearchResponse | null>(null);
  const [searchError, setSearchError] = useState<string | null>(null);

  // Inspection modal state
  const [selectedDoc, setSelectedDoc] = useState<DocumentMetadataResponse | null>(null);

  // Delete modal state
  const [docToDelete, setDocToDelete] = useState<DocumentMetadataResponse | null>(null);
  const [isDeleting, setIsDeleting] = useState<boolean>(false);
  const [deleteError, setDeleteError] = useState<string | null>(null);

  // Fetch documents list
  const fetchDocuments = useCallback(async () => {
    if (!token && !isAuthenticated) {
      setIsLoadingDocs(false);
      return;
    }
    setIsLoadingDocs(true);
    setDocsError(null);
    try {
      const data = await apiClient.listDocuments(undefined, token);
      setDocuments(data);
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : "Failed to load document library.";
      setDocsError(msg);
    } finally {
      setIsLoadingDocs(false);
    }
  }, [token, isAuthenticated]);

  useEffect(() => {
    if (!authLoading) {
      fetchDocuments();
    }
  }, [authLoading, fetchDocuments]);

  // Handle client-side file validation and upload
  const handleFileUpload = async (file: File) => {
    setUploadError(null);
    setUploadSuccess(null);

    // 1. Validate file extension and MIME
    const isPdf =
      file.name.toLowerCase().endsWith(".pdf") || file.type === "application/pdf";
    if (!isPdf) {
      setUploadError("Invalid file type: Only PDF documents (.pdf) are supported.");
      return;
    }

    // 2. Validate file size (10 MB maximum)
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setUploadError(
        `File too large (${formatBytes(file.size)}). Maximum permitted PDF size is 10 MB.`
      );
      return;
    }

    if (file.size === 0) {
      setUploadError("The selected PDF file is empty (0 bytes).");
      return;
    }

    setIsUploading(true);
    try {
      const newDoc = await apiClient.uploadDocument(file, token);
      setUploadSuccess(
        `"${newDoc.filename}" uploaded successfully and indexed into your private study store.`
      );
      await fetchDocuments();
    } catch (err: unknown) {
      let msg = "Failed to upload and index document.";
      if (err instanceof ApiError) {
        if (err.status === 401) {
          msg = "Session expired or authentication required. Please log in.";
        } else if (err.status === 413) {
          msg = "File size exceeds 10 MB backend limit.";
        } else if (err.status === 429) {
          msg = "Upload rate limit reached (max 10/min). Please wait a moment.";
        } else {
          msg = err.message;
        }
      } else if (err instanceof Error) {
        msg = err.message;
      }
      setUploadError(msg);
    } finally {
      setIsUploading(false);
      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    }
  };

  const onFileInputChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files;
    if (files && files.length > 0) {
      handleFileUpload(files[0]);
    }
  };

  const onDragOver = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const onDragLeave = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const onDrop = (e: React.DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    const files = e.dataTransfer.files;
    if (files && files.length > 0) {
      handleFileUpload(files[0]);
    }
  };

  // Handle semantic document search
  const handleSearch = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!searchQuery.trim()) return;

    setIsSearching(true);
    setSearchError(null);
    try {
      const res = await apiClient.searchDocuments(
        { query: searchQuery.trim(), max_results: 6, min_score: 0.35 },
        token
      );
      setSearchResults(res);
    } catch (err: unknown) {
      let msg = "Semantic search error.";
      if (err instanceof ApiError) {
        if (err.status === 401) msg = "Authentication required to search documents.";
        else if (err.status === 429) msg = "Search rate limit exceeded. Please wait.";
        else msg = err.message;
      }
      setSearchError(msg);
    } finally {
      setIsSearching(false);
    }
  };

  const clearSearch = () => {
    setSearchQuery("");
    setSearchResults(null);
    setSearchError(null);
  };

  // Handle document deletion
  const confirmDelete = async () => {
    if (!docToDelete) return;
    setIsDeleting(true);
    setDeleteError(null);
    try {
      await apiClient.deleteDocument(docToDelete.id, token);
      setDocToDelete(null);
      await fetchDocuments();
      if (searchResults) {
        // Clear search results if deleted document was searched
        setSearchResults(null);
      }
    } catch (err: unknown) {
      const msg = err instanceof ApiError ? err.message : "Failed to delete document.";
      setDeleteError(msg);
    } finally {
      setIsDeleting(false);
    }
  };

  // Unauthenticated view
  if (!authLoading && !isAuthenticated) {
    return (
      <div className="max-w-5xl mx-auto px-4 py-8 space-y-6">
        <PageHeader
          title="Document Library & Study Notes"
          description="Upload personal Class 10 PDF notes, chapter guides, and study materials for private multi-agent RAG retrieval."
        />
        <EmptyState
          icon={FileText}
          title="Student Authentication Required"
          description="Document management and multi-tenant vector retrieval are strictly scoped to authenticated student accounts to guarantee privacy and isolation."
          action={
            <div className="flex flex-wrap items-center justify-center gap-3">
              <Link href="/login">
                <Button variant="primary">Student Sign In</Button>
              </Link>
              <Link href="/register">
                <Button variant="secondary">Create Student Account</Button>
              </Link>
            </div>
          }
          agentInfo={{
            name: "Resource Agent",
            role: "Multi-tenant vector indexing and semantic retrieval",
            phase: "Phase 5D",
            status: "Protected",
          }}
        />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto px-4 py-6 sm:py-8 space-y-8">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">
        <PageHeader
          title="Document Library & Study Notes"
          description="Upload personal Class 10 PDF notes and guides. The Resource Agent chunks and indexes your notes for verified Teacher Agent grounding."
        />
        <div className="flex items-center gap-2">
          <Button
            variant="secondary"
            size="sm"
            onClick={fetchDocuments}
            disabled={isLoadingDocs}
            leftIcon={<RefreshCw className={`w-4 h-4 ${isLoadingDocs ? "animate-spin" : ""}`} />}
          >
            Refresh
          </Button>
          <Link href="/teacher">
            <Button
              variant="ai"
              size="sm"
              leftIcon={<GraduationCap className="w-4 h-4" />}
            >
              Ask AI Teacher
            </Button>
          </Link>
        </div>
      </div>

      {/* Upload Zone */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Upload className="w-5 h-5 text-[#2563EB]" />
              <CardTitle>Upload Study Notes (PDF)</CardTitle>
            </div>
            <Badge variant="neutral" size="sm">
              Max 10 MB • PDF Only
            </Badge>
          </div>
          <CardDescription>
            Documents are processed in an isolated sandbox, chunked with heading preservation, and indexed into your private vector store.
          </CardDescription>
        </CardHeader>
        <CardContent>
          {uploadError && (
            <div className="mb-4 p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-800 text-sm flex items-start gap-2.5">
              <AlertCircle className="w-5 h-5 text-red-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="font-semibold text-xs tracking-wider uppercase text-red-700">Upload Error</p>
                <p className="text-xs sm:text-sm mt-0.5">{uploadError}</p>
              </div>
              <button
                onClick={() => setUploadError(null)}
                className="text-red-500 hover:text-red-700"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          {uploadSuccess && (
            <div className="mb-4 p-3.5 rounded-xl bg-green-50 border border-green-200 text-green-800 text-sm flex items-start gap-2.5">
              <CheckCircle2 className="w-5 h-5 text-green-600 flex-shrink-0 mt-0.5" />
              <div className="flex-1">
                <p className="font-semibold text-xs tracking-wider uppercase text-green-700">Ready for Tutoring</p>
                <p className="text-xs sm:text-sm mt-0.5">{uploadSuccess}</p>
              </div>
              <button
                onClick={() => setUploadSuccess(null)}
                className="text-green-500 hover:text-green-700"
              >
                <X className="w-4 h-4" />
              </button>
            </div>
          )}

          <div
            onDragOver={onDragOver}
            onDragLeave={onDragLeave}
            onDrop={onDrop}
            className={`border-2 border-dashed rounded-2xl p-6 sm:p-10 text-center transition-all duration-150 ${
              isDragging
                ? "border-blue-500 bg-blue-50/70"
                : "border-[#E2E8F0] hover:border-blue-300 bg-slate-50/50"
            }`}
          >
            <input
              type="file"
              ref={fileInputRef}
              onChange={onFileInputChange}
              accept="application/pdf,.pdf"
              className="hidden"
            />

            <div className="w-14 h-14 rounded-2xl bg-blue-100 text-[#2563EB] flex items-center justify-center mx-auto mb-3 shadow-xs">
              <Upload className={`w-7 h-7 ${isUploading ? "animate-bounce" : ""}`} />
            </div>

            {isUploading ? (
              <div className="space-y-2">
                <p className="text-sm font-semibold text-[#172033]">
                  Uploading and indexing document...
                </p>
                <p className="text-xs text-[#64748B]">
                  Extracting text, generating semantic embeddings, and registering metadata in ChromaDB.
                </p>
                <div className="pt-2 flex justify-center">
                  <Spinner size="sm" label="Processing PDF..." />
                </div>
              </div>
            ) : (
              <div className="space-y-2">
                <p className="text-sm sm:text-base font-semibold text-[#172033]">
                  Drag and drop your study PDF here, or{" "}
                  <button
                    type="button"
                    onClick={() => fileInputRef.current?.click()}
                    className="text-[#2563EB] hover:text-[#1D4ED8] underline font-bold"
                  >
                    browse device
                  </button>
                </p>
                <p className="text-xs text-[#64748B] max-w-md mx-auto">
                  Supports Class 10 chapter notes, sample paper guides, and handwritten formula summaries up to 10 MB.
                </p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Semantic Search Section */}
      <Card>
        <CardHeader>
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Search className="w-5 h-5 text-[#2563EB]" />
              <CardTitle>Semantic Search Across Notes</CardTitle>
            </div>
            <Badge variant="teal" size="sm">
              ChromaDB Vector Retrieval
            </Badge>
          </div>
          <CardDescription>
            Search across concepts, definitions, and equations in your uploaded documents using natural language queries.
          </CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSearch} className="flex flex-col sm:flex-row gap-2.5">
            <div className="relative flex-1">
              <input
                type="text"
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                placeholder="e.g. How do acids react with metal carbonates? or Ohm's Law formula"
                disabled={isSearching || documents.length === 0}
                className="w-full pl-4 pr-10 py-2.5 text-sm rounded-xl border border-[#CBD5E1] bg-white focus:outline-none focus:ring-2 focus:ring-blue-500 disabled:bg-slate-100 disabled:opacity-60"
              />
              {searchQuery && (
                <button
                  type="button"
                  onClick={clearSearch}
                  className="absolute right-3 top-1/2 -translate-y-1/2 text-slate-400 hover:text-slate-600"
                >
                  <X className="w-4 h-4" />
                </button>
              )}
            </div>
            <div className="flex items-center gap-2">
              <Button
                type="submit"
                variant="primary"
                disabled={isSearching || !searchQuery.trim() || documents.length === 0}
                isLoading={isSearching}
                leftIcon={<Search className="w-4 h-4" />}
              >
                Search
              </Button>
              {searchResults && (
                <Button type="button" variant="ghost" size="sm" onClick={clearSearch}>
                  Clear
                </Button>
              )}
            </div>
          </form>

          {searchError && (
            <div className="mt-3 p-3 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2">
              <AlertCircle className="w-4 h-4" />
              <span>{searchError}</span>
            </div>
          )}

          {/* Search Results Display */}
          {searchResults && (
            <div className="mt-5 space-y-3 pt-4 border-t border-slate-100">
              <div className="flex items-center justify-between text-xs font-semibold text-[#64748B]">
                <span>Search Query: &ldquo;{searchResults.query}&rdquo;</span>
                <span>{searchResults.results_count} relevant excerpt(s) found</span>
              </div>

              {searchResults.results.length === 0 ? (
                <p className="text-xs text-slate-500 py-3 text-center">
                  No matching excerpts found with sufficient semantic similarity score.
                </p>
              ) : (
                <div className="grid grid-cols-1 md:grid-cols-2 gap-3 pt-1">
                  {searchResults.results.map((item: DocumentSearchResultItem) => {
                    const doc = documents.find((d) => d.id === item.document_id);
                    const docName = doc ? doc.filename : item.document_id;
                    const scorePct = Math.round(item.similarity_score * 100);

                    return (
                      <div
                        key={item.chunk_id}
                        className="p-3.5 rounded-xl border border-blue-100 bg-blue-50/40 hover:bg-blue-50/70 transition-colors space-y-2 text-left"
                      >
                        <div className="flex items-center justify-between text-[11px] text-[#64748B]">
                          <span className="font-semibold text-[#172033] truncate max-w-[200px]" title={docName}>
                            📄 {docName}
                          </span>
                          <Badge variant="teal" size="sm">
                            Page {item.page_number} • {scorePct}% Match
                          </Badge>
                        </div>
                        <p className="text-xs text-[#334155] leading-relaxed italic bg-white p-2.5 rounded-lg border border-blue-100/80">
                          &ldquo;{item.text}&rdquo;
                        </p>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>

      {/* Document Library Table/List */}
      <Card>
        <CardHeader>
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-2">
            <div>
              <CardTitle>My Uploaded Documents ({documents.length})</CardTitle>
              <CardDescription>
                Private study materials available for AI Teacher grounding and Resource Agent retrieval.
              </CardDescription>
            </div>
            {documents.length > 0 && (
              <Badge variant="primary" size="sm">
                Tenant: {student?.display_name || student?.id}
              </Badge>
            )}
          </div>
        </CardHeader>
        <CardContent>
          {docsError && (
            <div className="mb-4 p-3.5 rounded-xl bg-red-50 border border-red-200 text-red-800 text-sm flex items-center justify-between">
              <div className="flex items-center gap-2">
                <AlertCircle className="w-4 h-4 text-red-600" />
                <span>{docsError}</span>
              </div>
              <Button variant="ghost" size="sm" onClick={fetchDocuments}>
                Retry
              </Button>
            </div>
          )}

          {isLoadingDocs ? (
            <div className="py-12 flex justify-center">
              <Spinner size="md" label="Loading study documents..." />
            </div>
          ) : documents.length === 0 ? (
            <EmptyState
              icon={FileText}
              title="No Documents Uploaded Yet"
              description="Upload your CBSE Class 10 Science notes or textbook chapters above to enable AI Teacher document grounding."
              action={
                <Button
                  variant="primary"
                  onClick={() => fileInputRef.current?.click()}
                  leftIcon={<Upload className="w-4 h-4" />}
                >
                  Upload First PDF
                </Button>
              }
            />
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs border-collapse">
                <thead>
                  <tr className="border-b border-slate-200 text-slate-500 font-semibold uppercase tracking-wider text-[11px] bg-slate-50/70">
                    <th className="py-3 px-4">Document</th>
                    <th className="py-3 px-3">Status</th>
                    <th className="py-3 px-3">Size</th>
                    <th className="py-3 px-3">Pages / Chunks</th>
                    <th className="py-3 px-3">Uploaded</th>
                    <th className="py-3 px-4 text-right">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-100">
                  {documents.map((doc) => {
                    const isIndexed = doc.indexing_status === "INDEXED";
                    const isProcessing = doc.indexing_status === "PROCESSING";
                    const isFailed = doc.indexing_status === "FAILED";

                    return (
                      <tr key={doc.id} className="hover:bg-slate-50/60 transition-colors">
                        <td className="py-3.5 px-4 font-medium text-[#172033]">
                          <div className="flex items-center gap-2.5">
                            <div className="w-8 h-8 rounded-lg bg-blue-50 text-[#2563EB] flex items-center justify-center flex-shrink-0">
                              <FileText className="w-4 h-4" />
                            </div>
                            <div className="min-w-0">
                              <p className="truncate font-semibold text-sm max-w-[220px] sm:max-w-xs text-[#172033]" title={doc.filename}>
                                {doc.filename}
                              </p>
                              <p className="text-[10px] text-slate-400 font-mono truncate max-w-[220px]" title={doc.id}>
                                {doc.id}
                              </p>
                            </div>
                          </div>
                        </td>
                        <td className="py-3 px-3">
                          {isIndexed && (
                            <Badge variant="primary" size="sm" dot>
                              Indexed
                            </Badge>
                          )}
                          {isProcessing && (
                            <Badge variant="warning" size="sm" dot>
                              Processing
                            </Badge>
                          )}
                          {isFailed && (
                            <Badge variant="warning" size="sm" dot>
                              Failed
                            </Badge>
                          )}
                        </td>
                        <td className="py-3 px-3 text-slate-600 whitespace-nowrap">
                          {formatBytes(doc.file_size)}
                        </td>
                        <td className="py-3 px-3 text-slate-600 whitespace-nowrap">
                          {doc.page_count} pp • {doc.chunk_count} chunks
                        </td>
                        <td className="py-3 px-3 text-slate-500 whitespace-nowrap">
                          {new Date(doc.created_at).toLocaleDateString(undefined, {
                            month: "short",
                            day: "numeric",
                            year: "numeric",
                          })}
                        </td>
                        <td className="py-3 px-4 text-right whitespace-nowrap">
                          <div className="flex items-center justify-end gap-1.5">
                            <button
                              onClick={() => setSelectedDoc(doc)}
                              title="Inspect metadata"
                              className="p-1.5 text-slate-500 hover:text-blue-600 hover:bg-blue-50 rounded-lg transition-colors"
                            >
                              <Info className="w-4 h-4" />
                            </button>

                            <Link
                              href={`/teacher?docId=${encodeURIComponent(doc.id)}&docName=${encodeURIComponent(doc.filename)}`}
                              title="Ask Teacher about this document"
                              className="inline-flex items-center gap-1 px-2.5 py-1 text-xs font-semibold text-[#2563EB] hover:bg-blue-50 rounded-lg transition-colors"
                            >
                              <GraduationCap className="w-3.5 h-3.5" />
                              <span className="hidden sm:inline">Ask AI</span>
                            </Link>

                            <button
                              onClick={() => setDocToDelete(doc)}
                              title="Delete document"
                              className="p-1.5 text-slate-400 hover:text-red-600 hover:bg-red-50 rounded-lg transition-colors"
                            >
                              <Trash2 className="w-4 h-4" />
                            </button>
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Document Details Modal */}
      {selectedDoc && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-lg w-full border border-slate-200 shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="flex items-center justify-between p-5 border-b border-slate-100">
              <div className="flex items-center gap-2">
                <FileCheck className="w-5 h-5 text-[#2563EB]" />
                <h3 className="font-bold text-base text-[#172033]">Document Metadata</h3>
              </div>
              <button
                onClick={() => setSelectedDoc(null)}
                className="text-slate-400 hover:text-slate-600 p-1"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="p-5 space-y-3.5 text-xs text-[#334155]">
              <div className="grid grid-cols-3 gap-2 py-1.5 border-b border-slate-100">
                <span className="font-semibold text-slate-500">Filename:</span>
                <span className="col-span-2 font-mono break-all">{selectedDoc.filename}</span>
              </div>
              <div className="grid grid-cols-3 gap-2 py-1.5 border-b border-slate-100">
                <span className="font-semibold text-slate-500">Document ID:</span>
                <span className="col-span-2 font-mono text-[11px] break-all">{selectedDoc.id}</span>
              </div>
              <div className="grid grid-cols-3 gap-2 py-1.5 border-b border-slate-100">
                <span className="font-semibold text-slate-500">Student ID:</span>
                <span className="col-span-2 font-mono text-[11px] break-all">{selectedDoc.student_id}</span>
              </div>
              <div className="grid grid-cols-3 gap-2 py-1.5 border-b border-slate-100">
                <span className="font-semibold text-slate-500">File Size:</span>
                <span className="col-span-2">{formatBytes(selectedDoc.file_size)} ({selectedDoc.file_size.toLocaleString()} bytes)</span>
              </div>
              <div className="grid grid-cols-3 gap-2 py-1.5 border-b border-slate-100">
                <span className="font-semibold text-slate-500">Structure:</span>
                <span className="col-span-2">{selectedDoc.page_count} page(s) • {selectedDoc.chunk_count} semantic chunk(s)</span>
              </div>
              <div className="grid grid-cols-3 gap-2 py-1.5 border-b border-slate-100">
                <span className="font-semibold text-slate-500">Indexing Status:</span>
                <span className="col-span-2 font-semibold">
                  <Badge variant={selectedDoc.indexing_status === "INDEXED" ? "primary" : "warning"} size="sm">
                    {selectedDoc.indexing_status}
                  </Badge>
                </span>
              </div>
              <div className="grid grid-cols-3 gap-2 py-1.5 border-b border-slate-100">
                <span className="font-semibold text-slate-500">Indexed At:</span>
                <span className="col-span-2">{new Date(selectedDoc.created_at).toLocaleString()}</span>
              </div>
              {selectedDoc.error_message && (
                <div className="grid grid-cols-3 gap-2 py-1.5 text-red-600 bg-red-50 p-2 rounded-lg">
                  <span className="font-semibold">Error Details:</span>
                  <span className="col-span-2">{selectedDoc.error_message}</span>
                </div>
              )}
            </div>
            <div className="p-4 bg-slate-50 border-t border-slate-100 flex justify-end">
              <Button variant="secondary" size="sm" onClick={() => setSelectedDoc(null)}>
                Close
              </Button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {docToDelete && (
        <div className="fixed inset-0 z-50 bg-black/40 backdrop-blur-xs flex items-center justify-center p-4">
          <div className="bg-white rounded-2xl max-w-md w-full border border-slate-200 shadow-xl overflow-hidden animate-in fade-in zoom-in-95 duration-150">
            <div className="p-5 space-y-3">
              <div className="w-12 h-12 rounded-xl bg-red-100 text-red-600 flex items-center justify-center">
                <Trash2 className="w-6 h-6" />
              </div>
              <h3 className="font-bold text-base text-[#172033]">
                Delete Study Document?
              </h3>
              <p className="text-xs text-[#64748B] leading-relaxed">
                Are you sure you want to delete <strong className="text-[#172033]">&ldquo;{docToDelete.filename}&rdquo;</strong>?
                This action will delete the document file from disk and permanently purge all associated vector embeddings from the local AI search store.
              </p>

              {deleteError && (
                <div className="p-2.5 rounded-lg bg-red-50 border border-red-200 text-red-700 text-xs flex items-center gap-2">
                  <AlertCircle className="w-4 h-4 flex-shrink-0" />
                  <span>{deleteError}</span>
                </div>
              )}
            </div>
            <div className="p-4 bg-slate-50 border-t border-slate-100 flex items-center justify-end gap-2.5">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setDocToDelete(null)}
                disabled={isDeleting}
              >
                Cancel
              </Button>
              <Button
                variant="danger"
                size="sm"
                onClick={confirmDelete}
                isLoading={isDeleting}
              >
                Delete Document
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
