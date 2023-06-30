"use client";
import React, { useState } from "react";
import { Button, Form, Spinner, Stack  } from "react-bootstrap";
import { toast } from "react-toastify";
import download from "downloadjs";

export default function ConfigSideNav() {
  const [docs, setDocs] = useState([]);
  const [isLoading, setIsLoading] = useState(false);
  const [downloadInProgress, setdownloadInProgress] = useState(false);
  const [selectedFile, setSelectedFile] = useState(null);
  const [isUploading, setIsUploading] = useState(null);

  const ingestData = async () => {
    try {
      setIsLoading(true);
      const res = await fetch("http://localhost:5000/ingest");
      if (!res.ok) {
        // This will activate the closest `error.js` Error Boundary
        console.log(res);
        res.text().then(text => {toast.error("Error ingesting data: "+text);});
        setIsLoading(false);
      } else {
        const data = await res.json();
        console.log(data);
        toast.success("Ingested successfully");
        setIsLoading(false);
      }
    } catch (error) {
      console.error(error);
      toast.error("Error ingesting data");
      setIsLoading(false);
    }
  };

  const viewDocs = async () => {
    try {
      setIsLoading(true);
      const res = await fetch("http://localhost:5000/view_docs");
      if (!res.ok) {
        // This will activate the closest `error.js` Error Boundary
        console.log(res);
        res.text().then(text => {toast.error("Error loading documents: "+text);});
        setIsLoading(false);
      } else {
        const data = await res.json();
        console.log(data);
        setDocs(data);
        toast.success("List loaded successfully");
        setIsLoading(false);
      }
    } catch (error) {
      console.error(error);
      toast.error("Error loading documents");
      setIsLoading(false);
    }
  };

  const handleDelete = async (filename) => {
    await deleteDoc(filename);
    await viewDocs();
  };

  const deleteDoc = async (filename) => {
    try {
      setIsLoading(true);
      const res = await fetch("http://localhost:5000/delete_doc/"+filename, {method: 'DELETE'});
      const data = await res.json();
      if (!res.ok) {
        // This will activate the closest `error.js` Error Boundary
        console.log(res);
        toast.error("Error deleting the document: "+data["response"]);
        setIsLoading(false);
      } else {
        console.log(data);
        toast.success("Deleted successfully");
        setIsLoading(false);
      }
    } catch (error) {
      console.error(error);
      toast.error("Error deleting the document");
      setIsLoading(false);
    }
  };

  // const downloadDoc = async (filename) => {
  //   try {
  //     setdownloadInProgress(true);
  //     const res = await fetch("http://localhost:5000/source_documents/"+filename);
  //     if (!res.ok) {
  //       console.log(res);
  //       res.text().then(text => {toast.error("Error downloading the document: "+text);});
  //       setdownloadInProgress(false);
  //     } else {
  //       const blob = await res.blob();
  //       console.log("Downloaded successfully");
  //       download(blob, filename);
  //       setdownloadInProgress(false);
  //     }
  //   } catch (error) {
  //     console.error(error);
  //     toast.error("Error downloading the document");
  //     setdownloadInProgress(false);
  //   }
  // };

  const handleFileChange = (event) => {
    if(event.target.files[0]!=null){
      setSelectedFile(event.target.files[0]);
    }
  };

  const handleUpload = async () => {
    setIsUploading(true)
    try {
      const formData = new FormData();
      formData.append("document", selectedFile);

      const res = await fetch("http://localhost:5000/upload_doc", {
        method: "POST",
        body: formData,
      });
      const data = await res.json();

      if (!res.ok) {
        console.log(res);
        toast.error("Error uploading document: "+data["response"]);
        setSelectedFile(null); // Clear the selected file after successful upload
        document.getElementById("file-input").value = "";
        setIsUploading(false)
      } else {
        console.log(data);
        toast.success("Document Upload Successful");
        setSelectedFile(null); // Clear the selected file after successful upload
        document.getElementById("file-input").value = "";
        await viewDocs();
        setIsUploading(false);
      }
    } catch (error) {
      console.log(error);
      toast.error("Error uploading document");
      setSelectedFile(null); // Clear the selected file after successful upload
      document.getElementById("file-input").value = "";
      setIsUploading(false)
    }
  };

  return (
    <>
      <div className="mx-4 mt-3">
        <Form.Group className="mb-3">
          <Form.Label>Upload your documents</Form.Label>
          <Form.Control
            type="file"
            size="sm"
            onChange={handleFileChange}
            id="file-input"
          />
        </Form.Group>
        {isUploading? <div className="d-flex justify-content-center"><Spinner animation="border" /><span className="ms-3">uploading</span></div>:<Button onClick={(e) => handleUpload()}>Upload</Button>}
        {isLoading ? (
          <div className="d-flex justify-content-center"><Spinner animation="border" /><span className="ms-3">ingesting</span></div>
        ) : (
          <Button onClick={() => ingestData()}>Ingest Data</Button>
        )}
      </div>
      <div className="mx-4 mt-3">
        <p>Manage your documents</p>
        <Button onClick={() => viewDocs()}>Refresh</Button>
        <div className="mx-3 mt-2">
          {docs.length > 0
            ? (docs.map((doc) => (
                <Stack direction="horizontal" gap={2}>
                  <div>{doc}</div>
                  {/* <Button onClick={() => downloadDoc(doc)}>Download</Button> */}
                  <Button color="red" onClick={() => handleDelete(doc)}>Delete</Button>
                </Stack>)
              ))
            : (<div>Empty DB. Refresh to double check.</div>)
          }
        </div>
      </div>
    </>
  );
}
