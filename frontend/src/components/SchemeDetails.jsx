import { useState, useEffect, Fragment } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useAuth } from "@clerk/clerk-react";
import { fetchSchemeDetails } from "../services/api";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
import {
  ArrowLeft,
  Building2,
  Users,
  Bookmark,
  FileText,
  Gift,
  ShieldCheck,
  Ban,
  FileBadge2,
  CircleHelp,
  Link2,
  MessageSquareText,
  ExternalLink,
} from "lucide-react";

const SchemeDetails = () => {
  const { slug } = useParams();
  const navigate = useNavigate();
  const { getToken } = useAuth();
  const [scheme, setScheme] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let stale = false;
    const loadScheme = async () => {
      setLoading(true);
      try {
        const token = await getToken();
        const data = await fetchSchemeDetails(token, slug);
        if (!stale) setScheme(data);
      } catch (error) {
        if (!stale) {
          console.error("Failed to load scheme details", error);
          setScheme(null);
        }
      } finally {
        if (!stale) setLoading(false);
      }
    };
    loadScheme();
    return () => {
      stale = true;
    };
  }, [slug, getToken]);

  const getPrimitiveValue = (value) => {
    if (value === null || value === undefined || value === "") return "—";
    if (typeof value === "string" || typeof value === "number")
      return String(value);
    if (typeof value === "boolean") return value ? "Yes" : "No";
    if (typeof value === "object" && !Array.isArray(value)) {
      if (value.label) return String(value.label);
      if (
        value.value &&
        (typeof value.value === "string" || typeof value.value === "number")
      ) {
        return String(value.value);
      }
    }
    return null;
  };

  const toDisplayArray = (value) => {
    if (!value) return [];
    if (Array.isArray(value)) {
      return value
        .map((item) => getPrimitiveValue(item))
        .filter((item) => item && item !== "—");
    }
    const primitive = getPrimitiveValue(value);
    return primitive && primitive !== "—" ? [primitive] : [];
  };

  const renderSchemaItem = (item) => {
    if (!item) return null;

    // Handle simple strings
    if (typeof item === "string") {
      return <span>{item}</span>;
    }

    // Handle array of items (children)
    if (Array.isArray(item)) {
      return (
        <Fragment>
          {item.map((child, idx) => (
            <Fragment key={idx}>{renderSchemaItem(child)}</Fragment>
          ))}
        </Fragment>
      );
    }

    // Handle object structure
    if (typeof item === "object") {
      // Text node
      if (item.text) {
        if (item.type === "link") {
          return (
            <a
              href={item.link || item.url || item.text}
              target="_blank"
              rel="noreferrer"
              className="text-rose-500 hover:underline break-all"
            >
              {item.text}
            </a>
          );
        }
        return (
          <span className={item.bold ? "font-bold text-slate-900" : ""}>
            {item.text}
          </span>
        );
      }

      // Children node
      const children = item.children ? renderSchemaItem(item.children) : null;

      switch (item.type) {
        case "paragraph":
          return (
            <p className="text-slate-600 leading-relaxed mb-4 last:mb-0">
              {children}
            </p>
          );
        case "ol_list":
          return (
            <ol className="list-decimal pl-6 space-y-2 text-slate-600 mb-4 last:mb-0">
              {children}
            </ol>
          );
        case "ul_list":
          return (
            <ul className="list-disc pl-6 space-y-2 text-slate-600 mb-4 last:mb-0">
              {children}
            </ul>
          );
        case "list_item":
          return <li>{children}</li>;
        case "link":
          return (
            <a
              href={item.link || item.url}
              target="_blank"
              rel="noreferrer"
              className="text-rose-500 hover:underline break-all"
            >
              {children || item.link || item.url}
            </a>
          );
        default:
          // If it's a generic container or unknown type, just render children
          if (children) return <Fragment>{children}</Fragment>;

          // Fallback for key-value objects that are NOT part of the schema structure
          // e.g. MongoDB nested objects that don't follow the type/children pattern
          if (!item.type && !item.text && !item.children) {
            return (
              <div className="space-y-1">
                {Object.entries(item).map(([k, v]) => {
                  // Skip internal/system keys if any
                  if (k === "_id" || k === "slug") return null;
                  return (
                    <div key={k} className="flex flex-col sm:flex-row sm:gap-2">
                      <span className="font-semibold text-slate-700 capitalize min-w-fit">
                        {k.replace(/([A-Z])/g, " $1").trim()}:
                      </span>
                      <span className="text-slate-600">
                        {typeof v === "object" ? renderContent(v) : String(v)}
                      </span>
                    </div>
                  );
                })}
              </div>
            );
          }
          return null;
      }
    }
    return null;
  };

  const renderContent = (value) => {
    if (!value) return null;

    // 1. Handle Markdown String
    if (typeof value === "string") {
      return (
        <div className="prose prose-slate max-w-none text-slate-600 leading-relaxed">
          <ReactMarkdown remarkPlugins={[remarkGfm]}>{value}</ReactMarkdown>
        </div>
      );
    }

    // 2. Handle Structured Array (Schema or Strings)
    if (Array.isArray(value)) {
      if (value.length === 0) return null;

      // Check if this is a schema-structured array (objects with 'type' and 'children' or 'text')
      const isSchemaArray = value.some(
        (item) =>
          typeof item === "object" &&
          item !== null &&
          (item.type || item.text || item.children),
      );

      if (isSchemaArray) {
        return (
          <div className="space-y-4">
            {value.map((item, index) => (
              <div key={index}>{renderSchemaItem(item)}</div>
            ))}
          </div>
        );
      }

      // Check if array of strings
      const isStringArray = value.every((item) => typeof item === "string");
      if (isStringArray) {
        return (
          <ul className="list-disc pl-6 space-y-2 text-slate-600">
            {value.map((item, i) => (
              <li key={i}>{item}</li>
            ))}
          </ul>
        );
      }

      // Fallback for complex objects or mixed content (List[Dict])
      return (
        <div className="space-y-4">
          {value.map((item, i) => (
            <div
              key={i}
              className="bg-slate-50 p-4 rounded-lg border border-slate-200"
            >
              {renderSchemaItem(item)}
            </div>
          ))}
        </div>
      );
    }

    // 3. Handle Single Object (Schema or Generic)
    if (typeof value === "object") {
      return renderSchemaItem(value);
    }

    return <span className="text-slate-600">{String(value)}</span>;
  };

  // Helper to extract application URL from process
  const getApplyUrl = () => {
    if (!scheme?.applicationProcess) return null;
    // Check top-level url field if it exists
    const directUrl = scheme.applicationProcess.find((p) => p.url)?.url;
    if (directUrl) return directUrl;

    // Fallback: search in process steps for links
    // This is a heuristic; might need refinement based on actual data
    return null;
  };

  const tagItems = toDisplayArray(scheme?.basicDetails?.schemeCategory);
  const beneficiaryItems = toDisplayArray(
    scheme?.basicDetails?.targetBeneficiaries,
  );
  const references = toDisplayArray(scheme?.schemeContent?.references);
  const faqItems = Array.isArray(scheme?.faqs) ? scheme.faqs : [];
  const documentsRequired = toDisplayArray(
    scheme?.eligibilityCriteria?.documentsRequired ||
      scheme?.documentsRequired ||
      scheme?.requiredDocuments,
  );

  const applyUrl = getApplyUrl();

  // Priority: Markdown -> Structured List -> Plain Text
  const detailsContent =
    scheme?.schemeContent?.detailedDescription_md ||
    scheme?.schemeContent?.detailedDescription ||
    scheme?.schemeContent?.briefDescription;

  const eligibilityContent =
    scheme?.eligibilityCriteria?.eligibilityDescription_md ||
    scheme?.eligibilityCriteria?.eligibilityDescription;

  const exclusionsContent = scheme?.schemeContent?.exclusions;

  const sectionLinks = [
    { id: "details", label: "Details", icon: FileText },
    { id: "benefits", label: "Benefits", icon: Gift },
    { id: "eligibility", label: "Eligibility", icon: ShieldCheck },
    { id: "exclusions", label: "Exclusions", icon: Ban },
    {
      id: "application-process",
      label: "Application Process",
      icon: FileBadge2,
    },
    { id: "documents", label: "Documents Required", icon: FileBadge2 },
    { id: "faqs", label: "Frequently Asked Questions", icon: CircleHelp },
    { id: "sources", label: "Sources And References", icon: Link2 },
    { id: "feedback", label: "Feedback", icon: MessageSquareText },
  ];

  if (loading) {
    return (
      <div className="flex justify-center items-center h-screen bg-white">
        <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-rose-500"></div>
      </div>
    );
  }

  if (!scheme) {
    return (
      <div className="flex justify-center items-center h-screen bg-white">
        <p className="text-xl font-bold text-slate-500">Scheme not found</p>
      </div>
    );
  }

  return (
    <div className="bg-white font-['Manrope'] text-slate-900 min-h-screen py-10 px-6 lg:px-20">
      <main className="max-w-7xl mx-auto w-full">
        <div className="mb-8">
          <button
            onClick={() => navigate("/schemes")}
            className="inline-flex items-center gap-2 text-slate-600 hover:text-rose-500 transition-colors font-semibold"
          >
            <ArrowLeft size={20} />
            Back
          </button>
        </div>

        <div className="flex flex-col lg:flex-row gap-12">
          <aside className="w-full lg:w-72 shrink-0 flex flex-col gap-2 lg:sticky lg:top-24 self-start">
            {sectionLinks.map((item, index) => {
              const Icon = item.icon;
              return (
                <a
                  key={item.id}
                  href={`#${item.id}`}
                  className={`flex items-center gap-2 px-4 py-3 rounded-lg transition-colors border-l-4 ${
                    index === 0
                      ? "bg-rose-50 text-rose-500 font-bold border-rose-500"
                      : "text-slate-600 hover:bg-rose-50 hover:text-rose-500 font-medium border-transparent hover:border-rose-300"
                  }`}
                >
                  <Icon size={16} />
                  {item.label}
                </a>
              );
            })}
          </aside>

          <section className="flex-1 space-y-10">
            <div className="space-y-6 border-b border-rose-100 pb-10 relative">
              <button className="absolute top-0 right-0 p-2 text-rose-500 hover:bg-rose-50 rounded-full transition-colors">
                <Bookmark size={18} />
              </button>
              <div>
                <span className="text-slate-500 font-medium tracking-wide">
                  {scheme.basicDetails?.level?.label || "Government Scheme"}
                </span>
                <h1 className="text-4xl font-black tracking-tight mt-2 mb-4">
                  {scheme.basicDetails?.schemeName}
                </h1>
                <div className="flex flex-wrap gap-3">
                  {tagItems.map((tag, index) => (
                    <span
                      key={`${tag}-${index}`}
                      className="px-4 py-1.5 border border-rose-200 text-rose-500 text-sm font-semibold rounded-full bg-rose-50"
                    >
                      {tag}
                    </span>
                  ))}
                </div>
              </div>
              <div className="flex flex-wrap gap-4 pt-4">
                <a
                  href="#eligibility"
                  className="px-8 py-3 border-2 border-rose-500 text-rose-500 rounded-xl text-base font-bold hover:bg-rose-50 transition-colors"
                >
                  Check Eligibility
                </a>
                {applyUrl ? (
                  <a
                    href={applyUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="inline-flex items-center gap-2 px-8 py-3 bg-rose-500 text-white rounded-xl text-base font-bold hover:bg-rose-600 transition-all shadow-lg shadow-rose-200"
                  >
                    Apply Now
                    <ExternalLink size={16} />
                  </a>
                ) : (
                  <button
                    type="button"
                    className="px-8 py-3 bg-slate-300 text-slate-600 rounded-xl text-base font-bold cursor-not-allowed"
                  >
                    Apply Now
                  </button>
                )}
              </div>
            </div>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
              <div className="bg-slate-50 p-6 rounded-xl border border-slate-200">
                <h3 className="font-bold text-slate-900 mb-4 flex items-center gap-2">
                  <Building2 size={20} className="text-rose-500" />
                  Ministry
                </h3>
                <p className="text-slate-600 font-medium">
                  {scheme.basicDetails?.nodalMinistryName?.label || "—"}
                </p>
              </div>
              <div className="bg-slate-50 p-6 rounded-xl border border-slate-200">
                <h3 className="font-bold text-slate-900 mb-4 flex items-center gap-2">
                  <Users size={20} className="text-rose-500" />
                  Beneficiaries
                </h3>
                <div className="flex flex-wrap gap-2">
                  {beneficiaryItems.length > 0 ? (
                    beneficiaryItems.map((item, index) => (
                      <span
                        key={`${item}-${index}`}
                        className="px-2 py-1 bg-white rounded text-sm font-medium text-slate-600 border border-slate-200"
                      >
                        {item}
                      </span>
                    ))
                  ) : (
                    <p className="text-slate-500">No beneficiaries listed.</p>
                  )}
                </div>
              </div>
            </div>

            <div id="details" className="scroll-mt-32">
              <h2 className="text-2xl font-bold mb-4">Details</h2>
              {renderContent(detailsContent) || (
                <p className="text-slate-500">No details available.</p>
              )}
            </div>

            <div id="benefits" className="scroll-mt-32">
              <h2 className="text-2xl font-bold mb-4">Benefits</h2>
              {renderContent(scheme.schemeContent?.benefits) || (
                <p className="text-slate-500">No benefits details available.</p>
              )}
            </div>

            <div id="eligibility" className="scroll-mt-32">
              <h2 className="text-2xl font-bold mb-4">Eligibility</h2>
              {renderContent(eligibilityContent) || (
                <p className="text-slate-500">
                  No eligibility criteria available.
                </p>
              )}
            </div>

            <div id="exclusions" className="scroll-mt-32">
              <h2 className="text-2xl font-bold mb-4">Exclusions</h2>
              {renderContent(exclusionsContent) || (
                <p className="text-slate-500">No exclusions specified.</p>
              )}
            </div>

            <div id="application-process" className="scroll-mt-32">
              <h2 className="text-2xl font-bold mb-4">Application Process</h2>
              {Array.isArray(scheme.applicationProcess) &&
              scheme.applicationProcess.length > 0 ? (
                <div className="space-y-4">
                  {scheme.applicationProcess.map((step, idx) => (
                    <div
                      key={idx}
                      className="bg-white border border-slate-200 p-6 rounded-xl shadow-sm"
                    >
                      <h4 className="font-bold text-rose-500 mb-2 uppercase text-sm tracking-wider">
                        {step.mode || `Step ${idx + 1}`}
                      </h4>
                      <div className="text-slate-700">
                        {renderContent(step.process)}
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-slate-500">
                  No application process details available.
                </p>
              )}
            </div>

            <div id="documents" className="scroll-mt-32">
              <h2 className="text-2xl font-bold mb-4">Documents Required</h2>
              {documentsRequired.length > 0 ? (
                <div className="grid sm:grid-cols-2 gap-4">
                  {documentsRequired.map((item, index) => (
                    <div
                      key={`${item}-${index}`}
                      className="bg-white p-4 rounded-lg border border-rose-100 shadow-sm flex items-start gap-3"
                    >
                      <FileBadge2 size={18} className="text-rose-500 mt-0.5" />
                      <div>
                        <h4 className="font-bold text-sm">{item}</h4>
                      </div>
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-slate-500">
                  No documents listed in this scheme.
                </p>
              )}
            </div>

            <div id="faqs" className="scroll-mt-32">
              <h2 className="text-2xl font-bold mb-4">
                Frequently Asked Questions
              </h2>
              {faqItems.length > 0 ? (
                <div className="space-y-3">
                  {faqItems.map((item, index) => (
                    <div
                      key={`faq-${index}`}
                      className="bg-slate-50 border border-slate-200 rounded-lg p-4"
                    >
                      {renderContent(item)}
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-slate-500">
                  No FAQs available for this scheme.
                </p>
              )}
            </div>

            <div id="sources" className="scroll-mt-32">
              <h2 className="text-2xl font-bold mb-4">
                Sources And References
              </h2>
              {references.length > 0 ? (
                <ul className="space-y-2">
                  {references.map((reference, index) => (
                    <li
                      key={`${reference}-${index}`}
                      className="bg-slate-50 border border-slate-200 rounded-lg px-4 py-3 text-slate-700"
                    >
                      {reference}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-slate-500">
                  No references available for this scheme.
                </p>
              )}
            </div>

            <div
              id="feedback"
              className="scroll-mt-32 bg-rose-50 border border-rose-100 rounded-xl p-6"
            >
              <h2 className="text-2xl font-bold mb-3 text-slate-900">
                Feedback
              </h2>
              <p className="text-slate-600 mb-4">
                Help us improve this scheme page by sharing missing details or
                reporting outdated information.
              </p>
              <button
                type="button"
                className="inline-flex items-center gap-2 px-5 py-2.5 bg-rose-500 text-white rounded-lg font-semibold hover:bg-rose-600 transition-colors"
              >
                <MessageSquareText size={16} />
                Send Feedback
              </button>
            </div>
          </section>
        </div>
      </main>
    </div>
  );
};

export default SchemeDetails;
